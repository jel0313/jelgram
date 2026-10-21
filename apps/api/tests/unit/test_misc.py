"""UT:Webhook の署名・モデレーション・通知・ユーザーのスキーマ・ワーカーの処理。"""

import hashlib
import hmac
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.exceptions import UnauthorizedError
from app.moderation.service import find_blocked_words
from app.notifications import repository as notifications_repository
from app.notifications import service as notifications
from app.users.schemas import ProfileUpdate
from app.webhooks.router import verify_signature
from app.worker import handlers
from tests.fakes import FakeAI, FakePush, FakeStorage, make_image

SECRET = "s" * 32


def sign(body: bytes, ts: str) -> str:
    return hmac.new(SECRET.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()


class TestWebhookSignature:
    def test_valid(self) -> None:
        verify_signature(SECRET, "1000", b"{}", sign(b"{}", "1000"), now=1000)

    def test_tampered_body(self) -> None:
        with pytest.raises(UnauthorizedError, match="署名"):
            verify_signature(SECRET, "1000", b'{"x":1}', sign(b"{}", "1000"), now=1000)

    @pytest.mark.parametrize(("ts", "now"), [("1000", 1301), ("1000", 699), ("abc", 1000)])
    def test_old_or_bad_timestamp(self, ts: str, now: int) -> None:
        """5分(300秒)を超えたものは再送攻撃とみなす。境界の 300 秒は OK。"""
        with pytest.raises(UnauthorizedError, match="タイムスタンプ"):
            verify_signature(SECRET, ts, b"{}", sign(b"{}", ts), now=now)

    def test_boundary_300_seconds_is_ok(self) -> None:
        verify_signature(SECRET, "1000", b"{}", sign(b"{}", "1000"), now=1300)


class TestModeration:
    @pytest.mark.parametrize(
        ("text", "hit"), [("死ね", True), ("ＫＩＬＬ ＹＯＵＲＳＥＬＦ", True), ("元気?", False)]
    )
    def test_find_blocked_words(self, text: str, hit: bool) -> None:
        """全角・大文字でもすり抜けない。"""
        assert bool(find_blocked_words(text)) is hit

    @pytest.mark.parametrize(
        ("text", "expected"),
        [
            ('{"flagged": true, "reason": "差別"}', {"flagged": True, "reason": "差別"}),
            ('```json\n{"flagged": false}\n```', {"flagged": False}),
            ("判定できません", {}),
            ("{壊れた", {}),
        ],
    )
    def test_parse_moderation(self, text: str, expected: dict) -> None:  # type: ignore[type-arg]
        assert handlers.parse_moderation(text) == expected


class TestNotify:
    def test_self_action_is_not_notified(self, monkeypatch: pytest.MonkeyPatch) -> None:
        me = uuid4()
        monkeypatch.setattr(
            notifications_repository, "insert_notification", lambda *a, **k: pytest.fail("作らない")
        )
        notifications.notify(None, recipient_id=me, actor_id=me, type_="like", post_id=1)  # type: ignore[arg-type]

    def test_blocked_actor_is_not_notified(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(notifications_repository, "is_blocked_either_way", lambda *a: True)
        monkeypatch.setattr(
            notifications_repository, "insert_notification", lambda *a, **k: pytest.fail("作らない")
        )
        notifications.notify(None, recipient_id=uuid4(), actor_id=uuid4(), type_="like", post_id=1)  # type: ignore[arg-type]


class TestProfileUpdate:
    def test_username_is_lowercased(self) -> None:
        assert ProfileUpdate(username="Hanako_01").username == "hanako_01"

    @pytest.mark.parametrize("username", ["ab", "a" * 31, "hana-ko", "はなこ", "admin"])
    def test_invalid_usernames(self, username: str) -> None:
        """境界値:2文字・31文字はだめ。記号・日本語・予約語もだめ。"""
        with pytest.raises(ValidationError):
            ProfileUpdate(username=username)

    @pytest.mark.parametrize("username", ["abc", "a" * 30, "user_1"])
    def test_valid_usernames(self, username: str) -> None:
        ProfileUpdate(username=username)

    def test_bio_max_150(self) -> None:
        ProfileUpdate(bio="あ" * 150)
        with pytest.raises(ValidationError):
            ProfileUpdate(bio="あ" * 151)

    def test_empty_body(self) -> None:
        with pytest.raises(ValidationError):
            ProfileUpdate()


class FakeSession:
    def commit(self) -> None:
        pass


class TestWorkerHandlers:
    def test_media_process(self, monkeypatch: pytest.MonkeyPatch) -> None:
        storage = FakeStorage()
        storage.objects["u/a.jpg"] = (make_image("JPEG", (640, 480)), "image/jpeg")
        updated = {}
        monkeypatch.setattr(
            handlers.media_repository,
            "get_media",
            lambda s, mid: {"path": "u/a.jpg", "status": "pending", "content_type": "image/jpeg"},
        )
        monkeypatch.setattr(
            handlers.media_repository, "update_processed", lambda s, mid, **kw: updated.update(kw)
        )

        handlers.handle_media_process(FakeSession(), storage, {"media_id": str(uuid4())})  # type: ignore[arg-type]

        assert "u/a_thumb.webp" in storage.objects
        assert updated["status"] == "ready" and updated["thumbnail_path"] == "u/a_thumb.webp"

    def test_media_process_skips_done(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """冪等:処理済みならもう一度は加工しない。"""
        monkeypatch.setattr(
            handlers.media_repository, "get_media", lambda s, mid: {"status": "ready"}
        )
        handlers.handle_media_process(FakeSession(), FakeStorage(), {"media_id": str(uuid4())})  # type: ignore[arg-type]

    def test_notification_push_removes_invalid_subscription(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        removed = []
        monkeypatch.setattr(
            handlers.notifications_repository,
            "get_notification",
            lambda s, nid: {
                "id": nid,
                "type": "like",
                "recipient_id": uuid4(),
                "actor_display_name": "花子",
            },
        )
        monkeypatch.setattr(
            handlers.notifications_repository,
            "list_push_subscriptions",
            lambda s, uid: [{"id": 1, "endpoint": "ok"}, {"id": 2, "endpoint": "gone"}],
        )
        monkeypatch.setattr(
            handlers.notifications_repository,
            "delete_push_subscription_by_id",
            lambda s, sid: removed.append(sid),
        )
        push = FakePush(invalid_endpoints={"gone"})

        handlers.handle_notification_created(FakeSession(), push, {"notification_id": 5})  # type: ignore[arg-type]

        assert push.sent[0]["body"] == "花子 さんがあなたの投稿にいいねしました"
        assert removed == [2]

    def test_moderation_hides_flagged_post(self, monkeypatch: pytest.MonkeyPatch) -> None:
        hidden = []
        session = SimpleNamespace(
            execute=lambda *a: SimpleNamespace(scalar_one_or_none=lambda: "<b>投稿</b>"),
            commit=lambda: None,
        )
        monkeypatch.setattr(
            handlers.admin_service,
            "hide_post_automatically",
            lambda s, pid, src, reason: hidden.append((pid, src, reason)),
        )
        ai = FakeAI(reply='{"flagged": true, "reason": "脅迫"}')

        handlers.handle_post_moderate(session, ai, {"post_id": 3})  # type: ignore[arg-type]

        assert hidden == [(3, "ai", "脅迫")]
        assert "&lt;b&gt;" in ai.calls[0][1][0].text  # 投稿のタグは無害化して渡す

    def test_unknown_event_raises(self) -> None:
        dispatch = handlers.make_dispatcher(
            None,
            storage=FakeStorage(),
            ai=FakeAI(),
            push=FakePush(),
            settings=None,  # type: ignore[arg-type]
        )
        with pytest.raises(ValueError, match="未知"):
            dispatch("nope", {})
