"""UT:投稿のスキーマ・ハッシュタグ・サービス(repository は差し替え)。"""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from app.posts import repository, service
from app.posts.exceptions import (
    ContentNotAllowedError,
    NotPostOwnerError,
    PostNotFoundError,
    PostVersionConflictError,
)
from app.posts.hashtags import extract_hashtags, normalize_hashtag
from app.posts.repository import escape_like
from app.posts.schemas import PostCreate, PostPatch, PostReplace
from tests.fakes import FakeStorage

ME = uuid4()
OTHER = uuid4()
NOW = datetime(2026, 10, 22, tzinfo=UTC)


# ---------------------------------------------------------------- スキーマ(1-2〜1-4)


class TestPostCreate:
    def test_strips_whitespace(self) -> None:
        assert PostCreate(content="  こんにちは  ").content == "こんにちは"

    @pytest.mark.parametrize(
        ("content", "ok"),
        [("", False), ("   ", False), ("a", True), ("あ" * 500, True), ("あ" * 501, False)],
    )
    def test_length_boundaries(self, content: str, ok: bool) -> None:
        """境界値:0文字・空白だけ・1文字・500文字・501文字。"""
        if ok:
            PostCreate(content=content)
        else:
            with pytest.raises(ValidationError):
                PostCreate(content=content)

    def test_media_ids_max_10(self) -> None:
        PostCreate(content="a", media_ids=[uuid4() for _ in range(10)])
        with pytest.raises(ValidationError):
            PostCreate(content="a", media_ids=[uuid4() for _ in range(11)])

    def test_duplicate_media_ids(self) -> None:
        media_id = uuid4()
        with pytest.raises(ValidationError, match="同じ画像"):
            PostCreate(content="a", media_ids=[media_id, media_id])

    def test_extra_fields_are_rejected(self) -> None:
        """user_id などを送り込まれても受け付けない(マスアサインメント対策)。"""
        with pytest.raises(ValidationError):
            PostCreate.model_validate({"content": "a", "user_id": str(OTHER)})


class TestPostPatch:
    def test_only_sent_fields_are_set(self) -> None:
        body = PostPatch(content="new", version=1)
        assert body.model_dump(exclude_unset=True, exclude={"version"}) == {"content": "new"}

    def test_needs_at_least_one_field(self) -> None:
        with pytest.raises(ValidationError, match="1つ以上"):
            PostPatch(version=1)

    def test_null_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="null"):
            PostPatch.model_validate({"content": None, "version": 1})

    def test_put_requires_all_fields(self) -> None:
        with pytest.raises(ValidationError):
            PostReplace.model_validate({"content": "a", "version": 1})


class TestHashtags:
    @pytest.mark.parametrize(
        ("content", "expected"),
        [
            ("今日は #カレー と #Curry", ["カレー", "curry"]),
            ("#a #A #a", ["a"]),  # 重複・大文字小文字
            ("全角 ＃ラーメン も", ["ラーメン"]),
            ("タグなし", []),
            ("#" + "x" * 51, []),  # 長すぎるタグは無視
        ],
    )
    def test_extract(self, content: str, expected: list[str]) -> None:
        assert extract_hashtags(content) == expected

    def test_max_30(self) -> None:
        assert len(extract_hashtags(" ".join(f"#t{i}" for i in range(40)))) == 30

    def test_normalize(self) -> None:
        assert normalize_hashtag("#Curry") == "curry"


class TestEscapeLike:
    def test_special_characters(self) -> None:
        """% と _ を「ただの文字」として検索できるようにする。"""
        assert escape_like(r"100%_\x") == r"100\%\_\\x"


# ---------------------------------------------------------------- サービス


class FakeSession:
    def __init__(self) -> None:
        self.commits = 0
        self.rollbacks = 0

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def post_row(post_id: int = 1, author_id: UUID = ME, **overrides: Any) -> dict[str, Any]:
    return {
        "id": post_id,
        "content": "hello",
        "image_url": None,
        "created_at": NOW,
        "updated_at": NOW,
        "version": 1,
        "like_count": 0,
        "comment_count": 0,
        "comments_disabled": False,
        "author_id": author_id,
        "author_username": "me",
        "author_display_name": "わたし",
        "author_avatar_url": "https://google/avatar.png",
        "author_avatar_path": None,
        "liked_by_me": False,
        **overrides,
    }


@pytest.fixture
def repo(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """repository の関数を、メモリ上の簡単な実装に差し替える。"""
    state = SimpleNamespace(posts={1: post_row()}, owners={1: ME}, updated=None, notified=[])

    monkeypatch.setattr(repository, "get_post", lambda s, pid, viewer: state.posts.get(pid))
    monkeypatch.setattr(
        repository,
        "get_post_owner",
        lambda s, pid: (
            {"id": pid, "user_id": state.owners[pid], "version": 1} if pid in state.owners else None
        ),
    )
    monkeypatch.setattr(repository, "get_media_for_posts", lambda s, ids: [])
    monkeypatch.setattr(repository, "get_hashtags_for_posts", lambda s, ids: [])
    monkeypatch.setattr(repository, "insert_post", lambda s, uid, content: 1)
    monkeypatch.setattr(repository, "insert_post_media", lambda *a: None)
    monkeypatch.setattr(repository, "replace_hashtags", lambda *a: None)
    monkeypatch.setattr(
        repository, "update_post", lambda s, pid, version, values: 2 if version == 1 else None
    )
    monkeypatch.setattr(repository, "insert_like", lambda s, uid, pid: 1)
    monkeypatch.setattr(service.outbox, "enqueue", lambda *a, **k: None)
    monkeypatch.setattr(
        service.notifications, "notify", lambda session, **kwargs: state.notified.append(kwargs)
    )
    return state


class TestPostService:
    def test_create_post(self, repo: SimpleNamespace) -> None:
        session = FakeSession()
        response = service.create_post(session, FakeStorage(), ME, PostCreate(content="hello"), 60)  # type: ignore[arg-type]
        assert response.id == 1 and response.author.avatar_url == "https://google/avatar.png"
        assert session.commits == 1

    def test_create_post_with_blocked_word(self, repo: SimpleNamespace) -> None:
        with pytest.raises(ContentNotAllowedError):
            service.create_post(
                FakeSession(), FakeStorage(), ME, PostCreate(content="お前なんか死ね"), 60
            )  # type: ignore[arg-type]

    def test_get_missing_post_is_404(self, repo: SimpleNamespace) -> None:
        with pytest.raises(PostNotFoundError):
            service.get_post(FakeSession(), FakeStorage(), 999, ME, 60)  # type: ignore[arg-type]

    def test_update_by_other_user_is_403(self, repo: SimpleNamespace) -> None:
        """他人の投稿(見えている)は 403(7-1)。"""
        repo.owners[1] = OTHER
        with pytest.raises(NotPostOwnerError):
            service.update_post(
                FakeSession(), FakeStorage(), 1, ME, PostPatch(content="x", version=1), 60
            )  # type: ignore[arg-type]

    def test_update_of_invisible_post_is_404(self, repo: SimpleNamespace) -> None:
        """他人の見えない投稿(非公開・ブロック)は 404。存在を教えない。"""
        repo.owners[1] = OTHER
        repo.posts.clear()
        with pytest.raises(PostNotFoundError):
            service.update_post(
                FakeSession(), FakeStorage(), 1, ME, PostPatch(content="x", version=1), 60
            )  # type: ignore[arg-type]

    def test_stale_version_is_409(self, repo: SimpleNamespace) -> None:
        """楽観的ロック:古い version で更新すると 409(10-2)。"""
        session = FakeSession()
        with pytest.raises(PostVersionConflictError):
            service.update_post(
                session, FakeStorage(), 1, ME, PostPatch(content="x", version=5), 60
            )  # type: ignore[arg-type]
        assert session.rollbacks == 1 and session.commits == 0

    def test_like_notifies_author(self, repo: SimpleNamespace) -> None:
        repo.posts[1] = post_row(author_id=OTHER)
        result = service.like_post(FakeSession(), 1, ME)  # type: ignore[arg-type]
        assert result.liked_by_me is True and result.like_count == 1
        assert repo.notified == [
            {"recipient_id": OTHER, "actor_id": ME, "type_": "like", "post_id": 1}
        ]

    def test_second_like_does_not_notify(
        self, monkeypatch: pytest.MonkeyPatch, repo: SimpleNamespace
    ) -> None:
        monkeypatch.setattr(repository, "insert_like", lambda *a: None)  # いいね済み
        monkeypatch.setattr(repository, "get_like_count", lambda *a: 7)
        result = service.like_post(FakeSession(), 1, ME)  # type: ignore[arg-type]
        assert result.like_count == 7 and repo.notified == []

    def test_avatar_from_storage_is_signed(self, repo: SimpleNamespace) -> None:
        storage = FakeStorage()
        storage.objects["u/a.png"] = (b"", "image/png")
        repo.posts[1] = post_row(author_avatar_path="u/a.png")
        response = service.get_post(FakeSession(), storage, 1, ME, 60)  # type: ignore[arg-type]
        assert response.author.avatar_url == "https://storage.test/u/a.png?token=signed"


class TestPopularCache:
    def test_cache_is_used(self, monkeypatch: pytest.MonkeyPatch, repo: SimpleNamespace) -> None:
        import fakeredis

        calls = []
        monkeypatch.setattr(
            repository, "list_popular_post_ids", lambda s, since, limit: calls.append(1) or [1]
        )
        monkeypatch.setattr(repository, "get_posts_by_ids", lambda s, viewer, ids: [post_row()])
        redis = fakeredis.FakeRedis(decode_responses=True)

        for _ in range(3):
            service.get_popular_posts(FakeSession(), FakeStorage(), redis, ME, NOW, 60)  # type: ignore[arg-type]
        assert len(calls) == 1  # 2回目以降はキャッシュ

        service.invalidate_popular_cache(redis)
        service.get_popular_posts(FakeSession(), FakeStorage(), redis, ME, NOW, 60)  # type: ignore[arg-type]
        assert len(calls) == 2
