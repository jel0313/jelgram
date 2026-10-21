"""投稿・いいねの業務ロジック。

確定(commit)はここで行う。1つの操作 = 1つのトランザクション。
"""

import json
import logging
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from redis import Redis, RedisError
from sqlalchemy.orm import Session

from app.core import audit, idempotency, outbox
from app.core.schemas import CursorPage, OffsetPage, decode_cursor, encode_cursor
from app.media import repository as media_repository
from app.media import service as media_service
from app.media.exceptions import MediaNotUsableError
from app.media.storage import StorageClient
from app.moderation.service import find_blocked_words
from app.notifications import service as notifications
from app.posts import repository
from app.posts.constants import (
    POPULAR_POSTS_CACHE_KEY,
    POPULAR_POSTS_CACHE_SECONDS,
    POPULAR_POSTS_DAYS,
    POPULAR_POSTS_LIMIT,
)
from app.posts.exceptions import (
    ContentNotAllowedError,
    NotPostOwnerError,
    PostNotFoundError,
    PostVersionConflictError,
)
from app.posts.hashtags import extract_hashtags, normalize_hashtag
from app.posts.schemas import (
    Author,
    LikeResponse,
    PostCreate,
    PostPatch,
    PostReplace,
    PostResponse,
    PostSort,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- 応答の組み立て


def build_responses(
    session: Session, storage: StorageClient, rows: Sequence[Mapping[Any, Any]], expires_in: int
) -> list[PostResponse]:
    """投稿の行のリストから、画像・ハッシュタグ付きの PostResponse のリストを作る。

    画像・ハッシュタグは全投稿分をまとめて1回ずつ取る(N+1 対策。4-6)。
    """
    if not rows:
        return []
    post_ids = [row["id"] for row in rows]

    # ① 画像:投稿 id → 画像の行(並び順どおり)
    media_by_post: dict[int, list[Mapping[Any, Any]]] = defaultdict(list)
    for media_row in repository.get_media_for_posts(session, post_ids):
        media_by_post[media_row["post_id"]].append(media_row)

    # ② ハッシュタグ:投稿 id → 名前のリスト
    tags_by_post: dict[int, list[str]] = defaultdict(list)
    for tag_row in repository.get_hashtags_for_posts(session, post_ids):
        tags_by_post[tag_row["post_id"]].append(tag_row["name"])

    # ③ 署名付き URL:投稿の画像と作成者のアイコンを、まとめて1回で作る
    avatar_rows = [
        {"id": row["author_id"], "path": row["author_avatar_path"]}
        for row in rows
        if row["author_avatar_path"]
    ]
    all_media = [m for items in media_by_post.values() for m in items]
    signed = media_service.sign_media(storage, [*all_media, *avatar_rows], expires_in)

    result = []
    for row in rows:
        avatar = signed.get(row["author_id"])
        author = Author(
            id=row["author_id"],
            username=row["author_username"],
            display_name=row["author_display_name"],
            avatar_url=(avatar.url if avatar else None) or row["author_avatar_url"],
        )
        result.append(
            PostResponse(
                id=row["id"],
                content=row["content"],
                image_url=row["image_url"],
                media=[signed[m["id"]] for m in media_by_post[row["id"]]],
                hashtags=tags_by_post[row["id"]],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                author=author,
                like_count=row["like_count"],
                comment_count=row["comment_count"],
                liked_by_me=row["liked_by_me"],
                comments_disabled=row["comments_disabled"],
                version=row["version"],
            )
        )
    return result


def _cursor_page(
    session: Session,
    storage: StorageClient,
    rows: Sequence[Mapping[Any, Any]],
    limit: int,
    expires_in: int,
) -> CursorPage[PostResponse]:
    """limit + 1 件取った結果から、1ページ分と次のカーソルを作る。"""
    has_next = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1]["created_at"], rows[-1]["id"]) if has_next else None
    return CursorPage(
        items=build_responses(session, storage, rows, expires_in), next_cursor=next_cursor
    )


# ---------------------------------------------------------------- 取得


def get_post(
    session: Session, storage: StorageClient, post_id: int, viewer_id: UUID, expires_in: int
) -> PostResponse:
    """投稿を1件返す。見てはいけない投稿も「ない」と同じ 404(存在を推測させない)。"""
    row = repository.get_post(session, post_id, viewer_id)
    if row is None:
        raise PostNotFoundError
    return build_responses(session, storage, [row], expires_in)[0]


def get_timeline(
    session: Session,
    storage: StorageClient,
    viewer_id: UUID,
    cursor: str | None,
    limit: int,
    expires_in: int,
) -> CursorPage[PostResponse]:
    """全体のタイムライン(新しい順)。"""
    rows = repository.list_timeline(
        session, viewer_id, decode_cursor(cursor) if cursor else None, limit
    )
    return _cursor_page(session, storage, rows, limit, expires_in)


def get_feed(
    session: Session,
    storage: StorageClient,
    viewer_id: UUID,
    cursor: str | None,
    limit: int,
    expires_in: int,
) -> CursorPage[PostResponse]:
    """フォロー中の人と自分の投稿(4-2)。"""
    rows = repository.list_feed(
        session, viewer_id, decode_cursor(cursor) if cursor else None, limit
    )
    return _cursor_page(session, storage, rows, limit, expires_in)


def get_user_posts(
    session: Session,
    storage: StorageClient,
    viewer_id: UUID,
    author_id: UUID,
    sort: PostSort,
    limit: int,
    offset: int,
    expires_in: int,
) -> OffsetPage[PostResponse]:
    """ユーザーの投稿一覧(4-1)。非公開アカウントで見る権限がなければ0件。"""
    rows, total = repository.list_user_posts(session, viewer_id, author_id, sort, limit, offset)
    return OffsetPage(
        items=build_responses(session, storage, rows, expires_in),
        total=total,
        limit=limit,
        offset=offset,
    )


def get_hashtag_posts(
    session: Session,
    storage: StorageClient,
    viewer_id: UUID,
    tag: str,
    cursor: str | None,
    limit: int,
    expires_in: int,
) -> CursorPage[PostResponse]:
    rows = repository.list_hashtag_posts(
        session, viewer_id, normalize_hashtag(tag), decode_cursor(cursor) if cursor else None, limit
    )
    return _cursor_page(session, storage, rows, limit, expires_in)


def search_posts(
    session: Session,
    storage: StorageClient,
    viewer_id: UUID,
    query: str,
    limit: int,
    offset: int,
    expires_in: int,
) -> list[PostResponse]:
    rows = repository.search_posts(session, viewer_id, query, limit, offset)
    return build_responses(session, storage, rows, expires_in)


def get_popular_posts(
    session: Session,
    storage: StorageClient,
    redis: Redis,
    viewer_id: UUID,
    now: datetime,
    expires_in: int,
) -> list[PostResponse]:
    """人気の投稿(13-1)。重い集計の結果(id の並び)だけを Redis に 60 秒キャッシュする。

    いいね済みかどうかは閲覧者ごとに違うので、キャッシュには入れず毎回 DB から取る。
    Redis が落ちていても、キャッシュなしで動く。
    """
    post_ids = _read_cached_ids(redis)
    if post_ids is None:
        since = now - timedelta(days=POPULAR_POSTS_DAYS)
        post_ids = repository.list_popular_post_ids(session, since, POPULAR_POSTS_LIMIT)
        _write_cached_ids(redis, post_ids)

    rows = repository.get_posts_by_ids(session, viewer_id, post_ids)
    order = {post_id: i for i, post_id in enumerate(post_ids)}
    rows = sorted(rows, key=lambda row: order[row["id"]])
    return build_responses(session, storage, rows, expires_in)


def _read_cached_ids(redis: Redis) -> list[int] | None:
    try:
        cached = redis.get(POPULAR_POSTS_CACHE_KEY)
    except RedisError:
        return None
    return json.loads(cached) if cached else None  # type: ignore[arg-type]


def _write_cached_ids(redis: Redis, post_ids: list[int]) -> None:
    try:
        redis.set(POPULAR_POSTS_CACHE_KEY, json.dumps(post_ids), ex=POPULAR_POSTS_CACHE_SECONDS)
    except RedisError:
        logger.warning("人気投稿をキャッシュできませんでした")


def invalidate_popular_cache(redis: Redis) -> None:
    """投稿の削除・非表示で、キャッシュを消す(13-2)。消せなくても 60 秒で切れる。"""
    try:
        redis.delete(POPULAR_POSTS_CACHE_KEY)
    except RedisError:
        logger.warning("人気投稿のキャッシュを消せませんでした")


# ---------------------------------------------------------------- 作成・編集・削除


def create_post(
    session: Session,
    storage: StorageClient,
    user_id: UUID,
    body: PostCreate,
    expires_in: int,
    idempotency_key: str | None = None,
) -> PostResponse:
    """投稿を作る(3-1)。冪等性キーがあれば、二重投稿にならない(10-4)。"""
    if find_blocked_words(body.content):
        raise ContentNotAllowedError

    if idempotency_key:
        stored = idempotency.begin(
            session,
            user_id,
            idempotency_key,
            idempotency.request_hash(body.model_dump(mode="json")),
        )
        if stored is not None:
            session.rollback()
            return PostResponse.model_validate(stored.body)

    # 画像は「自分がアップロードした・まだ投稿に使っていない」ものだけ(他人の画像を付けさせない)
    if body.media_ids:
        usable = media_repository.get_owned_unused_media(session, body.media_ids, user_id)
        if len(usable) != len(body.media_ids):
            raise MediaNotUsableError

    post_id = repository.insert_post(session, user_id, body.content)
    repository.insert_post_media(session, post_id, body.media_ids)
    repository.replace_hashtags(session, post_id, extract_hashtags(body.content))
    outbox.enqueue(session, outbox.POST_MODERATE, {"post_id": post_id})

    row = repository.get_post(session, post_id, user_id)
    if row is None:
        raise PostNotFoundError
    response = build_responses(session, storage, [row], expires_in)[0]
    if idempotency_key:
        idempotency.save(session, user_id, idempotency_key, 201, response.model_dump(mode="json"))
    session.commit()
    return response


def _get_own_post(session: Session, post_id: int, user_id: UUID) -> Mapping[Any, Any]:
    """自分の投稿を取る(7-1)。他人の投稿なら 403、ない・見えないなら 404。"""
    owner = repository.get_post_owner(session, post_id)
    if owner is None:
        raise PostNotFoundError
    if owner["user_id"] != user_id:
        # 見えない投稿(非公開・ブロック)なら、存在自体を教えない
        if repository.get_post(session, post_id, user_id) is None:
            raise PostNotFoundError
        raise NotPostOwnerError
    return owner


def update_post(
    session: Session,
    storage: StorageClient,
    post_id: int,
    user_id: UUID,
    body: PostReplace | PostPatch,
    expires_in: int,
) -> PostResponse:
    """投稿を編集する(3-4)。PUT は全項目、PATCH は送られた項目だけを変える。"""
    _get_own_post(session, post_id, user_id)

    if isinstance(body, PostPatch):
        values = body.model_dump(exclude_unset=True, exclude={"version"})  # 送られた項目だけ
    else:
        values = body.model_dump(exclude={"version"})  # 全項目
    if "content" in values and find_blocked_words(values["content"]):
        raise ContentNotAllowedError

    new_version = repository.update_post(session, post_id, body.version, values)
    if new_version is None:
        session.rollback()
        raise PostVersionConflictError(details={"your_version": body.version})
    if "content" in values:
        repository.replace_hashtags(session, post_id, extract_hashtags(values["content"]))
        outbox.enqueue(session, outbox.POST_MODERATE, {"post_id": post_id})

    row = repository.get_post(session, post_id, user_id)
    if row is None:
        raise PostNotFoundError
    session.commit()
    return build_responses(session, storage, [row], expires_in)[0]


def delete_post(session: Session, redis: Redis, post_id: int, user_id: UUID) -> None:
    """投稿を削除する(3-5・3-6・10-1)。

    DB の変更(論理削除・いいね・コメント・画像の行)は1つのトランザクションで行う。
    ストレージのファイルはロールバックできないので、確定後にワーカーが消す(Outbox)。
    """
    _get_own_post(session, post_id, user_id)
    try:
        paths = repository.soft_delete_post(session, post_id)
        if paths:
            outbox.enqueue(session, outbox.MEDIA_DELETE, {"paths": paths})
        audit.record(
            session, actor_id=user_id, action="post.delete", target_type="post", target_id=post_id
        )
        session.commit()
    except Exception:
        session.rollback()  # 途中で失敗したら、全部なかったことにする
        raise
    invalidate_popular_cache(redis)


# ---------------------------------------------------------------- いいね


def _ensure_visible(session: Session, post_id: int, viewer_id: UUID) -> Mapping[Any, Any]:
    row = repository.get_post(session, post_id, viewer_id)
    if row is None:
        raise PostNotFoundError
    return row


def like_post(session: Session, post_id: int, user_id: UUID) -> LikeResponse:
    """いいねする(3-7)。いいね済みでもエラーにしない(同じ結果になる = 冪等)。"""
    post = _ensure_visible(session, post_id, user_id)
    count = repository.insert_like(session, user_id, post_id)
    if count is None:
        count = repository.get_like_count(session, post_id)
    else:
        notifications.notify(
            session, recipient_id=post["author_id"], actor_id=user_id, type_="like", post_id=post_id
        )
    session.commit()
    return LikeResponse(post_id=post_id, like_count=count, liked_by_me=True)


def unlike_post(session: Session, post_id: int, user_id: UUID) -> LikeResponse:
    """いいねを取り消す。いいねしていなくてもエラーにしない。"""
    _ensure_visible(session, post_id, user_id)
    count = repository.delete_like(session, user_id, post_id)
    if count is None:
        count = repository.get_like_count(session, post_id)
    session.commit()
    return LikeResponse(post_id=post_id, like_count=count, liked_by_me=False)


# ---------------------------------------------------------------- 通報


def report_post(session: Session, post_id: int, reporter_id: UUID, reason: str) -> None:
    """投稿を通報する(7-5)。管理者が GET /admin/reports で確認する。"""
    _ensure_visible(session, post_id, reporter_id)
    repository.insert_report(session, reporter_id, post_id, reason)
    session.commit()
