"""UT:ユーザー・コメント・管理者・チャット準備・直接アップロードの service。

repository は差し替える。
"""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError

from app.admin import repository as admin_repository
from app.admin import service as admin_service
from app.auth.dependencies import CurrentUser, get_current_user
from app.chat import repository as chat_repository
from app.chat import service as chat_service
from app.chat.schemas import ChatRequest
from app.comments import repository as comments_repository
from app.comments import service as comments_service
from app.comments.exceptions import (
    CommentNotFoundError,
    CommentsDisabledError,
    NotCommentOwnerError,
)
from app.comments.schemas import CommentCreate, CommentUpdate
from app.core import idempotency
from app.core.config import get_settings
from app.core.db import get_db
from app.media import repository as media_repository
from app.media import service as media_service
from app.media.exceptions import MediaNotFoundError, UnsupportedImageError
from app.posts.exceptions import ContentNotAllowedError, PostNotFoundError
from app.users import repository as users_repository
from app.users import service as users_service
from app.users.exceptions import (
    CannotFollowSelfError,
    FollowRequestNotFoundError,
    UsernameTakenError,
    UserNotFoundError,
)
from app.users.schemas import ProfileUpdate
from tests.fakes import FakeStorage, make_image

ME, OTHER = uuid4(), uuid4()
NOW = datetime(2026, 10, 22, tzinfo=UTC)


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


@pytest.fixture
def no_side_effects(monkeypatch: pytest.MonkeyPatch) -> list[dict[str, Any]]:
    """通知・Outbox・監査ログを記録だけにする。"""
    calls: list[dict[str, Any]] = []
    for module in (users_service, comments_service):
        if hasattr(module, "notifications"):
            monkeypatch.setattr(
                module.notifications, "notify", lambda s, **kw: calls.append({"notify": kw})
            )
    monkeypatch.setattr("app.core.outbox.enqueue", lambda s, t, p: calls.append({"outbox": t}))
    monkeypatch.setattr(
        "app.core.audit.record", lambda s, **kw: calls.append({"audit": kw["action"]})
    )
    return calls


# ---------------------------------------------------------------- ユーザー


def base_profile(user_id: UUID, *, private: bool = False) -> dict[str, Any]:
    return {
        "id": user_id,
        "username": "hanako",
        "display_name": "花子",
        "avatar_url": None,
        "avatar_path": None,
        "bio": "",
        "is_private": private,
        "created_at": NOW,
        "follower_count": 1,
        "following_count": 2,
        "post_count": 3,
    }


@pytest.fixture
def users(
    monkeypatch: pytest.MonkeyPatch, no_side_effects: list[dict[str, Any]]
) -> SimpleNamespace:
    state = SimpleNamespace(
        ids={"hanako": OTHER, "me": ME},
        profiles={OTHER: base_profile(OTHER), ME: base_profile(ME)},
        follows={},
        db_reads=0,
        calls=no_side_effects,
    )

    def get_profile_base(session: Any, user_id: UUID) -> dict[str, Any] | None:
        state.db_reads += 1
        return state.profiles.get(user_id)

    monkeypatch.setattr(
        users_repository, "find_user_id_by_username", lambda s, u, v: state.ids.get(u)
    )
    monkeypatch.setattr(users_repository, "get_profile_base", get_profile_base)
    monkeypatch.setattr(
        users_repository,
        "get_relation",
        lambda s, v, t: {
            "follow_status": state.follows.get((v, t)),
            "follows_me": False,
            "blocked_by_me": False,
        },
    )

    def insert_follow(session: Any, a: UUID, b: UUID, status: str) -> bool:
        if (a, b) in state.follows:
            return False
        state.follows[(a, b)] = status
        return True

    monkeypatch.setattr(users_repository, "insert_follow", insert_follow)
    monkeypatch.setattr(
        users_repository,
        "get_email_target",
        lambda s, uid: {"email": "h@example.com", "display_name": "花子"},
    )
    return state


class TestUsersService:
    def test_profile_is_cached(self, users: SimpleNamespace) -> None:
        """2回目はキャッシュから読む(DB に行かない)。"""
        redis = fakeredis.FakeRedis(decode_responses=True)
        for _ in range(2):
            profile = users_service.get_profile(None, redis, FakeStorage(), "hanako", ME, 60)  # type: ignore[arg-type]
        assert profile.username == "hanako" and profile.follow_status == "none"
        assert users.db_reads == 1

    def test_unknown_user(self, users: SimpleNamespace) -> None:
        with pytest.raises(UserNotFoundError):
            users_service.get_profile(None, fakeredis.FakeRedis(), FakeStorage(), "nobody", ME, 60)  # type: ignore[arg-type]

    def test_follow_public_account(self, users: SimpleNamespace) -> None:
        response, email = users_service.follow(FakeSession(), fakeredis.FakeRedis(), ME, "hanako")  # type: ignore[arg-type]
        assert users.follows[(ME, OTHER)] == "accepted" and response.follow_status == "following"
        assert email is not None and email.subject == "[jelgram] 新しいフォロワー"
        assert {"notify": {"recipient_id": OTHER, "actor_id": ME, "type_": "follow"}} in users.calls

    def test_follow_private_account_is_pending(self, users: SimpleNamespace) -> None:
        users.profiles[OTHER] = base_profile(OTHER, private=True)
        response, email = users_service.follow(FakeSession(), fakeredis.FakeRedis(), ME, "hanako")  # type: ignore[arg-type]
        assert response.follow_status == "pending"
        assert email is not None and "リクエスト" in email.subject

    def test_second_follow_sends_nothing(self, users: SimpleNamespace) -> None:
        users_service.follow(FakeSession(), fakeredis.FakeRedis(), ME, "hanako")  # type: ignore[arg-type]
        users.calls.clear()
        _, email = users_service.follow(FakeSession(), fakeredis.FakeRedis(), ME, "hanako")  # type: ignore[arg-type]
        assert email is None and users.calls == []

    def test_cannot_follow_self(self, users: SimpleNamespace) -> None:
        with pytest.raises(CannotFollowSelfError):
            users_service.follow(FakeSession(), fakeredis.FakeRedis(), ME, "me")  # type: ignore[arg-type]

    def test_username_taken(self, monkeypatch: pytest.MonkeyPatch, users: SimpleNamespace) -> None:
        def update_profile(session: Any, user_id: UUID, values: dict[str, Any]) -> None:
            raise IntegrityError("update", {}, Exception('duplicate key "profiles_username_key"'))

        monkeypatch.setattr(users_repository, "update_profile", update_profile)
        session = FakeSession()
        with pytest.raises(UsernameTakenError):
            users_service.update_profile(
                session,
                fakeredis.FakeRedis(),
                FakeStorage(),
                ME,
                ProfileUpdate(username="taken"),
                60,  # type: ignore[arg-type]
            )
        assert session.rollbacks == 1

    def test_answer_missing_request(
        self, monkeypatch: pytest.MonkeyPatch, users: SimpleNamespace
    ) -> None:
        monkeypatch.setattr(users_repository, "lock_follow_request", lambda *a: False)
        with pytest.raises(FollowRequestNotFoundError):
            users_service.answer_follow_request(
                FakeSession(), fakeredis.FakeRedis(), ME, OTHER, approve=True
            )  # type: ignore[arg-type]

    def test_approve_request_notifies(
        self, monkeypatch: pytest.MonkeyPatch, users: SimpleNamespace
    ) -> None:
        accepted = []
        monkeypatch.setattr(users_repository, "lock_follow_request", lambda *a: True)
        monkeypatch.setattr(
            users_repository, "accept_follow", lambda s, a, b: accepted.append((a, b))
        )
        users_service.answer_follow_request(
            FakeSession(), fakeredis.FakeRedis(), ME, OTHER, approve=True
        )  # type: ignore[arg-type]
        assert accepted == [(OTHER, ME)]
        assert users.calls[0]["notify"]["type_"] == "follow_accepted"

    def test_private_follow_list_is_hidden(
        self, monkeypatch: pytest.MonkeyPatch, users: SimpleNamespace
    ) -> None:
        monkeypatch.setattr(users_repository, "can_view_content", lambda *a: False)
        page = users_service.list_follow_users(None, ME, "hanako", "followers", 10, 0)  # type: ignore[arg-type]
        assert page.total == 0 and page.items == []

    def test_delete_account(self, monkeypatch: pytest.MonkeyPatch, users: SimpleNamespace) -> None:
        """退会:ファイル削除とユーザー削除を Outbox に積み、監査ログを残す。"""
        monkeypatch.setattr(
            users_repository, "anonymize_and_delete_content", lambda s, uid: ["a.png"]
        )
        session = FakeSession()
        users_service.delete_account(session, fakeredis.FakeRedis(), ME)  # type: ignore[arg-type]
        assert {"outbox": "media.delete"} in users.calls and {"outbox": "user.purge"} in users.calls
        assert {"audit": "user.delete"} in users.calls and session.commits == 1


# ---------------------------------------------------------------- コメント


def comment_row(**overrides: Any) -> dict[str, Any]:
    return {
        "id": 10,
        "post_id": 1,
        "content": "c",
        "created_at": NOW,
        "updated_at": NOW,
        "user_id": OTHER,
        "post_owner_id": ME,
        "author_id": OTHER,
        "author_username": "o",
        "author_display_name": "O",
        "author_avatar_url": None,
        **overrides,
    }


@pytest.fixture
def comments(
    monkeypatch: pytest.MonkeyPatch, no_side_effects: list[dict[str, Any]]
) -> SimpleNamespace:
    state = SimpleNamespace(
        post={"id": 1, "user_id": ME, "comments_disabled": False},
        comment=comment_row(),
        calls=no_side_effects,
    )
    monkeypatch.setattr(comments_repository, "get_visible_post", lambda s, pid, v: state.post)
    monkeypatch.setattr(comments_repository, "get_comment", lambda s, cid: state.comment)
    monkeypatch.setattr(comments_repository, "insert_comment", lambda *a: 10)
    monkeypatch.setattr(comments_repository, "update_comment", lambda *a: None)
    monkeypatch.setattr(comments_repository, "soft_delete_comment", lambda *a: None)
    return state


class TestCommentsService:
    def test_create_notifies_post_owner(self, comments: SimpleNamespace) -> None:
        response = comments_service.create_comment(
            FakeSession(), 1, OTHER, CommentCreate(content="c")
        )  # type: ignore[arg-type]
        assert response.id == 10 and response.can_delete is True
        assert comments.calls[0]["notify"]["recipient_id"] == ME

    def test_create_on_invisible_post(self, comments: SimpleNamespace) -> None:
        comments.post = None
        with pytest.raises(PostNotFoundError):
            comments_service.create_comment(FakeSession(), 1, OTHER, CommentCreate(content="c"))  # type: ignore[arg-type]

    def test_comments_disabled_except_owner(self, comments: SimpleNamespace) -> None:
        comments.post = {**comments.post, "comments_disabled": True}
        with pytest.raises(CommentsDisabledError):
            comments_service.create_comment(FakeSession(), 1, OTHER, CommentCreate(content="c"))  # type: ignore[arg-type]
        comments_service.create_comment(FakeSession(), 1, ME, CommentCreate(content="c"))  # type: ignore[arg-type]

    def test_blocked_word(self, comments: SimpleNamespace) -> None:
        with pytest.raises(ContentNotAllowedError):
            comments_service.create_comment(FakeSession(), 1, OTHER, CommentCreate(content="死ね"))  # type: ignore[arg-type]

    def test_only_author_can_edit(self, comments: SimpleNamespace) -> None:
        with pytest.raises(NotCommentOwnerError):
            comments_service.update_comment(FakeSession(), 10, ME, CommentUpdate(content="x"))  # type: ignore[arg-type]
        assert (
            comments_service.update_comment(FakeSession(), 10, OTHER, CommentUpdate(content="x")).id
            == 10
        )  # type: ignore[arg-type]

    @pytest.mark.parametrize(
        ("actor", "allowed", "audited"),
        [("author", True, False), ("post_owner", True, True), ("stranger", False, False)],
    )
    def test_delete_permissions(
        self, comments: SimpleNamespace, actor: str, allowed: bool, audited: bool
    ) -> None:
        user = {"author": OTHER, "post_owner": ME, "stranger": uuid4()}[actor]
        if allowed:
            comments_service.delete_comment(FakeSession(), 10, user)  # type: ignore[arg-type]
        else:
            with pytest.raises(NotCommentOwnerError):
                comments_service.delete_comment(FakeSession(), 10, user)  # type: ignore[arg-type]
        assert ({"audit": "comment.delete_by_post_owner"} in comments.calls) is audited

    def test_get_comment(self, comments: SimpleNamespace) -> None:
        """見てよいコメントなら、その1件を返す(3-2)。"""
        response = comments_service.get_comment(FakeSession(), 10, ME)  # type: ignore[arg-type]
        assert response.id == 10
        assert response.content == "c"
        assert response.can_delete is True

    def test_get_comment_not_found(self, comments: SimpleNamespace) -> None:
        """コメントが無ければ CommentNotFoundError(3-2)。"""
        comments.comment = None
        with pytest.raises(CommentNotFoundError):
            comments_service.get_comment(FakeSession(), 10, ME)  # type: ignore[arg-type]

    def test_get_comment_route(
        self, app: FastAPI, monkeypatch: pytest.MonkeyPatch, comments: SimpleNamespace
    ) -> None:
        """GET /api/v1/comments/{comment_id} が 200 で返す(3-2。完成済みのテスト)。"""
        app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=ME)
        app.dependency_overrides[get_db] = lambda: FakeSession()
        expected = comments_service._to_response(comment_row(), ME)
        monkeypatch.setattr(comments_service, "get_comment", lambda s, cid, viewer: expected)
        res = TestClient(app).get("/api/v1/comments/10")
        assert res.status_code == 200
        assert res.json()["id"] == 10

    def test_missing_comment(self, comments: SimpleNamespace) -> None:
        comments.comment = None
        with pytest.raises(CommentNotFoundError):
            comments_service.delete_comment(FakeSession(), 10, ME)  # type: ignore[arg-type]

    def test_list_with_cursor(
        self, monkeypatch: pytest.MonkeyPatch, comments: SimpleNamespace
    ) -> None:
        rows = [comment_row(id=i) for i in (1, 2, 3)]
        seen = {}

        def list_comments(
            s: Any, pid: int, viewer: UUID, after_id: int | None, limit: int
        ) -> list[dict[str, Any]]:
            seen["after_id"] = after_id
            return rows

        monkeypatch.setattr(comments_repository, "list_comments", list_comments)
        page = comments_service.list_comments(None, 1, ME, "7", 2)  # type: ignore[arg-type]
        assert (
            seen["after_id"] == 7
            and [c.id for c in page.items] == [1, 2]
            and page.next_cursor == "2"
        )


# ---------------------------------------------------------------- 管理者


class TestAdminService:
    @pytest.fixture
    def admin(
        self, monkeypatch: pytest.MonkeyPatch, no_side_effects: list[dict[str, Any]]
    ) -> SimpleNamespace:
        state = SimpleNamespace(
            report={"id": 1, "post_id": 5, "status": "open"},
            hidden=[],
            resolved=[],
            calls=no_side_effects,
        )
        monkeypatch.setattr(admin_repository, "lock_report", lambda s, rid: state.report)
        monkeypatch.setattr(
            admin_repository,
            "set_post_hidden",
            lambda s, pid, hidden: state.hidden.append((pid, hidden)) or True,
        )
        monkeypatch.setattr(
            admin_repository,
            "resolve_reports_for_post",
            lambda s, pid, a, st: state.resolved.append(st),
        )
        monkeypatch.setattr(
            admin_repository, "resolve_report", lambda s, rid, a, st: state.resolved.append(st)
        )
        monkeypatch.setattr(
            admin_repository,
            "insert_system_report",
            lambda s, pid, reason: state.resolved.append(reason),
        )
        return state

    def test_hide_post(self, admin: SimpleNamespace) -> None:
        admin_service.resolve_report(FakeSession(), 1, ME, "hide_post")  # type: ignore[arg-type]
        assert admin.hidden == [(5, True)] and admin.resolved == ["resolved"]
        assert {"audit": "report.hide_post"} in admin.calls

    def test_dismiss(self, admin: SimpleNamespace) -> None:
        admin_service.resolve_report(FakeSession(), 1, ME, "dismiss")  # type: ignore[arg-type]
        assert admin.hidden == [] and admin.resolved == ["dismissed"]

    def test_already_resolved(self, admin: SimpleNamespace) -> None:
        admin.report = {**admin.report, "status": "resolved"}
        with pytest.raises(admin_service.ReportAlreadyResolvedError):
            admin_service.resolve_report(FakeSession(), 1, ME, "dismiss")  # type: ignore[arg-type]

    def test_missing_report(self, admin: SimpleNamespace) -> None:
        admin.report = None
        with pytest.raises(admin_service.ReportNotFoundError):
            admin_service.resolve_report(FakeSession(), 1, ME, "dismiss")  # type: ignore[arg-type]

    def test_auto_hide_creates_report(self, admin: SimpleNamespace) -> None:
        admin_service.hide_post_automatically(None, 5, "ai", "脅迫")  # type: ignore[arg-type]
        assert admin.resolved == ["[ai] 脅迫"] and {"audit": "post.auto_hide"} in admin.calls

    def test_suspend_unknown_user(
        self, monkeypatch: pytest.MonkeyPatch, admin: SimpleNamespace
    ) -> None:
        monkeypatch.setattr(admin_repository, "set_user_status", lambda *a: False)
        with pytest.raises(UserNotFoundError):
            admin_service.set_user_suspended(FakeSession(), OTHER, ME, suspended=True)  # type: ignore[arg-type]


# ---------------------------------------------------------------- チャットの準備


class TestChatPrepare:
    @pytest.fixture
    def chat(self, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
        state = SimpleNamespace(
            post={"id": 1, "content": "猫", "author_display_name": "花子"}, saved=[], locked=[]
        )
        monkeypatch.setattr(chat_repository, "get_visible_post", lambda s, pid, v: state.post)
        monkeypatch.setattr(chat_repository, "lock_user", lambda s, u: state.locked.append(u))
        monkeypatch.setattr(chat_service, "check_rate_limit", lambda *a: None)
        monkeypatch.setattr(
            chat_repository, "insert_message", lambda s, **kw: state.saved.append(kw)
        )
        monkeypatch.setattr(
            chat_repository, "get_history", lambda *a: [{"role": "user", "content": "どう?"}]
        )
        return state

    def test_prepare_with_post(self, chat: SimpleNamespace) -> None:
        session = FakeSession()
        prepared = chat_service.prepare(
            session,
            ME,
            ChatRequest(message="どう?", session_id="s", post_id=1),
            NOW,
            get_settings(),  # type: ignore[arg-type]
        )
        assert chat.locked == [ME] and chat.saved[0]["role"] == "user" and session.commits == 1
        assert prepared.messages[-1].text.startswith('<post author="花子">')

    def test_missing_post(self, chat: SimpleNamespace) -> None:
        chat.post = None
        with pytest.raises(PostNotFoundError):
            chat_service.prepare(
                FakeSession(),
                ME,
                ChatRequest(message="?", session_id="s", post_id=9),
                NOW,
                get_settings(),
            )  # type: ignore[arg-type]
        assert chat.saved == []

    def test_blocked_words_are_not_saved(self, chat: SimpleNamespace) -> None:
        with pytest.raises(ContentNotAllowedError):
            chat_service.prepare(
                FakeSession(), ME, ChatRequest(message="死ね", session_id="s"), NOW, get_settings()
            )  # type: ignore[arg-type]
        assert chat.saved == []


# ---------------------------------------------------------------- 直接アップロードの完了(9-7)


class TestCompleteUpload:
    @pytest.fixture
    def media(self, monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
        media_id = uuid4()
        state = SimpleNamespace(
            id=media_id,
            row={
                "id": media_id,
                "owner_id": ME,
                "path": "me/a.png",
                "thumbnail_path": None,
                "status": "pending",
                "width": None,
                "height": None,
                "content_type": "image/png",
                "size_bytes": 1,
                "created_at": NOW,
            },
            updates=[],
        )
        monkeypatch.setattr(media_repository, "get_media", lambda s, mid: state.row)
        monkeypatch.setattr(
            media_repository, "update_processed", lambda s, mid, **kw: state.updates.append(kw)
        )
        monkeypatch.setattr("app.core.outbox.enqueue", lambda *a: None)
        return state

    def test_valid_upload(self, media: SimpleNamespace) -> None:
        storage = FakeStorage()
        storage.objects["me/a.png"] = (make_image("PNG"), "image/png")
        media_service.complete_upload(
            FakeSession(), storage, owner_id=ME, media_id=media.id, expires_in=60
        )  # type: ignore[arg-type]
        assert media.updates[0]["width"] == 40

    def test_invalid_upload_is_deleted(self, media: SimpleNamespace) -> None:
        storage = FakeStorage()
        storage.objects["me/a.png"] = (b"not image", "image/png")
        with pytest.raises(UnsupportedImageError):
            media_service.complete_upload(
                FakeSession(), storage, owner_id=ME, media_id=media.id, expires_in=60
            )  # type: ignore[arg-type]
        assert "me/a.png" not in storage.objects and media.updates == [{"status": "failed"}]

    def test_other_users_media(self, media: SimpleNamespace) -> None:
        with pytest.raises(MediaNotFoundError):
            media_service.complete_upload(
                FakeSession(), FakeStorage(), owner_id=OTHER, media_id=media.id, expires_in=60
            )  # type: ignore[arg-type]

    def test_not_uploaded_yet(self, media: SimpleNamespace) -> None:
        with pytest.raises(MediaNotFoundError):
            media_service.complete_upload(
                FakeSession(), FakeStorage(), owner_id=ME, media_id=media.id, expires_in=60
            )  # type: ignore[arg-type]


# ---------------------------------------------------------------- 冪等性キー


class FakeResult:
    def __init__(self, value: Any) -> None:
        self.value = value

    def one_or_none(self) -> Any:
        return self.value

    def mappings(self) -> "FakeResult":
        return self

    def one(self) -> Any:
        return self.value


class TestIdempotency:
    def session(self, *results: Any) -> SimpleNamespace:
        values = iter(results)
        return SimpleNamespace(execute=lambda *a: FakeResult(next(values)))

    def test_first_time(self) -> None:
        assert idempotency.begin(self.session(("k",)), ME, "k", "h") is None  # type: ignore[arg-type]

    def test_replay(self) -> None:
        stored = {"request_hash": "h", "response_status": 201, "response_body": {"id": 1}}
        result = idempotency.begin(self.session(None, stored), ME, "k", "h")  # type: ignore[arg-type]
        assert result == idempotency.StoredResponse(201, {"id": 1})

    def test_different_body(self) -> None:
        stored = {"request_hash": "other", "response_status": 201, "response_body": {}}
        with pytest.raises(idempotency.IdempotencyKeyReusedError):
            idempotency.begin(self.session(None, stored), ME, "k", "h")  # type: ignore[arg-type]

    def test_in_progress(self) -> None:
        stored = {"request_hash": "h", "response_status": None, "response_body": None}
        with pytest.raises(idempotency.ConflictError):
            idempotency.begin(self.session(None, stored), ME, "k", "h")  # type: ignore[arg-type]

    def test_hash_ignores_key_order(self) -> None:
        assert idempotency.request_hash({"a": 1, "b": 2}) == idempotency.request_hash(
            {"b": 2, "a": 1}
        )
