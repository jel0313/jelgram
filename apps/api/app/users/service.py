"""ユーザー・フォロー・ブロック・退会の業務ロジック。"""

import contextlib
import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from redis import Redis, RedisError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import audit, outbox
from app.core.schemas import OffsetPage
from app.media import repository as media_repository
from app.media import service as media_service
from app.media.storage import StorageClient
from app.notifications import service as notifications
from app.posts.repository import escape_like
from app.posts.schemas import Author
from app.users import repository
from app.users.constants import PROFILE_CACHE_KEY, PROFILE_CACHE_SECONDS
from app.users.exceptions import (
    CannotFollowSelfError,
    FollowRequestNotFoundError,
    UsernameTakenError,
    UserNotFoundError,
)
from app.users.schemas import (
    AccountExport,
    FollowRequest,
    FollowResponse,
    FollowStatus,
    MeResponse,
    ProfileUpdate,
    UserProfile,
    UserSearchResult,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------- キャッシュ(13-1・13-2)


def _cache_key(user_id: UUID) -> str:
    return PROFILE_CACHE_KEY.format(user_id=user_id)


def invalidate_profile_cache(redis: Redis, *user_ids: UUID) -> None:
    """プロフィールやフォロー数が変わったら、キャッシュを消す。次に読んだ人が作り直す。"""
    try:
        redis.delete(*[_cache_key(u) for u in user_ids])
    except RedisError:
        logger.warning("プロフィールのキャッシュを消せませんでした")


def _get_profile_base(session: Session, redis: Redis, user_id: UUID) -> dict[str, Any] | None:
    """プロフィールの共通部分を、キャッシュ → DB の順で取る(キャッシュアサイド)。"""
    try:
        cached = redis.get(_cache_key(user_id))
        if cached:
            return dict(json.loads(cached))  # type: ignore[arg-type]
    except RedisError:
        logger.warning("Redis に接続できないため、キャッシュを使わずに読みます")
    row = repository.get_profile_base(session, user_id)
    if row is None:
        return None
    data = dict(row)
    with contextlib.suppress(RedisError):  # 書けなくても、次回また DB から読むだけ
        redis.set(_cache_key(user_id), json.dumps(data, default=str), ex=PROFILE_CACHE_SECONDS)
    return data


# ---------------------------------------------------------------- プロフィール


def _avatar_url(storage: StorageClient, row: Mapping[Any, Any], expires_in: int) -> str | None:
    if row.get("avatar_path"):
        signed = media_service.sign_media(
            storage, [{"id": row["id"], "path": row["avatar_path"]}], expires_in
        )
        return signed[row["id"]].url
    avatar_url: str | None = row.get("avatar_url")
    return avatar_url


def resolve_username(session: Session, username: str, viewer_id: UUID) -> UUID:
    user_id = repository.find_user_id_by_username(session, username, viewer_id)
    if user_id is None:
        raise UserNotFoundError
    return user_id


def get_profile(
    session: Session,
    redis: Redis,
    storage: StorageClient,
    username: str,
    viewer_id: UUID,
    expires_in: int,
) -> UserProfile:
    user_id = resolve_username(session, username, viewer_id)
    base = _get_profile_base(session, redis, user_id)
    if base is None:
        raise UserNotFoundError
    relation = repository.get_relation(session, viewer_id, user_id)
    return UserProfile(
        id=base["id"],
        username=base["username"],
        display_name=base["display_name"],
        avatar_url=_avatar_url(storage, base, expires_in),
        bio=base["bio"],
        is_private=base["is_private"],
        follower_count=base["follower_count"],
        following_count=base["following_count"],
        post_count=base["post_count"],
        created_at=base["created_at"],
        follow_status=_follow_status(relation["follow_status"]),
        follows_me=relation["follows_me"],
        blocked_by_me=relation["blocked_by_me"],
    )


def _follow_status(status: str | None) -> FollowStatus:
    return {"accepted": "following", "pending": "pending"}.get(status or "", "none")  # type: ignore[return-value]


def get_me(session: Session, storage: StorageClient, user_id: UUID, expires_in: int) -> MeResponse:
    row = repository.get_me(session, user_id)
    if row is None:
        raise UserNotFoundError
    return MeResponse(
        id=row["id"],
        username=row["username"],
        display_name=row["display_name"],
        avatar_url=_avatar_url(storage, row, expires_in),
        email=row["email"],
        bio=row["bio"],
        is_private=row["is_private"],
        role=row["role"],
        created_at=row["created_at"],
    )


def update_profile(
    session: Session,
    redis: Redis,
    storage: StorageClient,
    user_id: UUID,
    body: ProfileUpdate,
    expires_in: int,
) -> MeResponse:
    values = body.model_dump(exclude_unset=True)
    try:
        repository.update_profile(session, user_id, values)
        if values.get("is_private") is False:
            repository.accept_all_pending(session, user_id)
        session.commit()
    except IntegrityError as e:
        # ユーザー名の一意制約(2-5)。先に「使われているか」を調べるより確実(同時登録にも強い)
        session.rollback()
        if "profiles_username_key" in str(e.orig):
            raise UsernameTakenError from e
        raise
    invalidate_profile_cache(redis, user_id)
    return get_me(session, storage, user_id, expires_in)


def update_avatar(
    session: Session,
    redis: Redis,
    storage: StorageClient,
    user_id: UUID,
    *,
    data: bytes,
    filename: str | None,
    content_type: str | None,
    expires_in: int,
) -> MeResponse:
    """プロフィール画像を差し替え、古い画像を消す(9-9)。"""
    old = repository.get_avatar(session, user_id)
    uploaded = media_service.upload_media(
        session,
        storage,
        owner_id=user_id,
        data=data,
        filename=filename,
        content_type=content_type,
        expires_in=expires_in,
    )
    repository.update_profile(session, user_id, {"avatar_media_id": uploaded.id})
    if old is not None:
        # 行は今消し、ファイルは確定後にワーカーが消す(Outbox)
        media_repository.delete_media(session, old["id"])
        paths = [p for p in (old["path"], old["thumbnail_path"]) if p]
        outbox.enqueue(session, outbox.MEDIA_DELETE, {"paths": paths})
    session.commit()
    invalidate_profile_cache(redis, user_id)
    return get_me(session, storage, user_id, expires_in)


def search_users(
    session: Session, viewer_id: UUID, query: str, limit: int
) -> list[UserSearchResult]:
    rows = repository.search_users(session, viewer_id, f"%{escape_like(query.lower())}%", limit)
    return [UserSearchResult(**row) for row in rows]


# ---------------------------------------------------------------- フォロー


@dataclass(frozen=True)
class FollowEmail:
    """フォローされた人に送るメール(router が BackgroundTasks で送る。11-3)。"""

    to: str
    subject: str
    body: str


def follow(
    session: Session, redis: Redis, follower_id: UUID, username: str
) -> tuple[FollowResponse, FollowEmail | None]:
    """フォローする。非公開アカウントなら承認待ち(pending)になる(7-3)。"""
    followee_id = resolve_username(session, username, follower_id)
    if followee_id == follower_id:
        raise CannotFollowSelfError
    base = repository.get_profile_base(session, followee_id)
    if base is None:
        raise UserNotFoundError
    status = "pending" if base["is_private"] else "accepted"
    created = repository.insert_follow(session, follower_id, followee_id, status)
    if created:
        notifications.notify(
            session,
            recipient_id=followee_id,
            actor_id=follower_id,
            type_="follow_request" if status == "pending" else "follow",
        )
    session.commit()
    invalidate_profile_cache(redis, follower_id, followee_id)
    relation = repository.get_relation(session, follower_id, followee_id)
    response = FollowResponse(follow_status=_follow_status(relation["follow_status"]))

    email = None
    target = repository.get_email_target(session, followee_id) if created else None
    if target is not None and target["email"]:
        follower = repository.get_profile_base(session, follower_id)
        name = follower["display_name"] if follower else "だれか"
        pending = status == "pending"
        email = FollowEmail(
            to=target["email"],
            subject="[jelgram] フォローリクエストが届きました"
            if pending
            else "[jelgram] 新しいフォロワー",
            body=(
                f"{target['display_name']} さん\n\n{name} さんが"
                + ("フォローリクエストを送りました。" if pending else "あなたをフォローしました。")
            ),
        )
    return response, email


def unfollow(session: Session, redis: Redis, follower_id: UUID, username: str) -> None:
    followee_id = resolve_username(session, username, follower_id)
    repository.delete_follow(session, follower_id, followee_id)
    session.commit()
    invalidate_profile_cache(redis, follower_id, followee_id)


def list_follow_requests(session: Session, user_id: UUID) -> list[FollowRequest]:
    return [
        FollowRequest(
            user=Author(
                id=row["id"],
                username=row["username"],
                display_name=row["display_name"],
                avatar_url=row["avatar_url"],
            ),
            created_at=row["created_at"],
        )
        for row in repository.list_follow_requests(session, user_id)
    ]


def answer_follow_request(
    session: Session, redis: Redis, user_id: UUID, follower_id: UUID, *, approve: bool
) -> None:
    """フォローリクエストを承認・拒否する。行ロックで二重の処理を防ぐ(10-3)。"""
    if not repository.lock_follow_request(session, follower_id, user_id):
        session.rollback()
        raise FollowRequestNotFoundError
    if approve:
        repository.accept_follow(session, follower_id, user_id)
        notifications.notify(
            session, recipient_id=follower_id, actor_id=user_id, type_="follow_accepted"
        )
    else:
        repository.delete_follow(session, follower_id, user_id)
    session.commit()
    invalidate_profile_cache(redis, user_id, follower_id)


def list_follow_users(
    session: Session,
    viewer_id: UUID,
    username: str,
    direction: str,
    limit: int,
    offset: int,
) -> OffsetPage[Author]:
    """フォロワー・フォロー中の一覧。非公開アカウントは、見てよい人にだけ見せる。"""
    user_id = resolve_username(session, username, viewer_id)
    if not repository.can_view_content(session, viewer_id, user_id):
        return OffsetPage(items=[], total=0, limit=limit, offset=offset)
    rows, total = repository.list_follow_users(session, user_id, direction, limit, offset)
    return OffsetPage(
        items=[Author(**row) for row in rows], total=total, limit=limit, offset=offset
    )


# ---------------------------------------------------------------- ブロック


def block(session: Session, redis: Redis, blocker_id: UUID, username: str) -> None:
    blocked_id = repository.get_user_id_any(session, username)
    if blocked_id is None:
        raise UserNotFoundError
    if blocked_id == blocker_id:
        raise CannotFollowSelfError
    repository.insert_block(session, blocker_id, blocked_id)
    session.commit()
    invalidate_profile_cache(redis, blocker_id, blocked_id)


def unblock(session: Session, redis: Redis, blocker_id: UUID, username: str) -> None:
    blocked_id = repository.get_user_id_any(session, username)
    if blocked_id is None:
        raise UserNotFoundError
    repository.delete_block(session, blocker_id, blocked_id)
    session.commit()
    invalidate_profile_cache(redis, blocker_id, blocked_id)


def list_blocks(session: Session, user_id: UUID) -> list[Author]:
    return [Author(**row) for row in repository.list_blocks(session, user_id)]


# ---------------------------------------------------------------- 退会・エクスポート


def delete_account(session: Session, redis: Redis, user_id: UUID) -> None:
    """退会する(21-2)。

    ① 同じトランザクションで:プロフィールの匿名化・投稿などの削除・Outbox への登録
    ② 確定後にワーカーが:ストレージのファイル削除 → Supabase Auth のユーザー削除
    """
    paths = repository.anonymize_and_delete_content(session, user_id)
    if paths:
        outbox.enqueue(session, outbox.MEDIA_DELETE, {"paths": paths})
    outbox.enqueue(session, outbox.USER_PURGE, {"user_id": str(user_id)})
    audit.record(
        session, actor_id=user_id, action="user.delete", target_type="user", target_id=user_id
    )
    session.commit()
    invalidate_profile_cache(redis, user_id)


_EXPORT_QUERIES = {
    "posts": """select id, content, created_at, updated_at, like_count, comment_count
                from posts where user_id = :id and deleted_at is null order by id""",
    "comments": """select id, post_id, content, created_at from comments
                   where user_id = :id and deleted_at is null order by id""",
    "likes": "select post_id, created_at from likes where user_id = :id order by created_at",
    "following": """select a.username, f.status, f.created_at from follows f
                    join profiles a on a.id = f.followee_id where f.follower_id = :id""",
    "followers": """select a.username, f.status, f.created_at from follows f
                    join profiles a on a.id = f.follower_id where f.followee_id = :id""",
    "chat_messages": """select session_id, role, content, post_id, created_at from chat_messages
                        where user_id = :id order by id""",
}


def export_account(session: Session, user_id: UUID, now: datetime) -> AccountExport:
    """自分のデータを全部 JSON で返す(21-3)。"""
    me = repository.get_me(session, user_id)
    if me is None:
        raise UserNotFoundError
    profile = {k: v for k, v in dict(me).items() if k != "avatar_path"}
    data = {
        name: repository.export_rows(session, sql, user_id) for name, sql in _EXPORT_QUERIES.items()
    }
    return AccountExport(exported_at=now, profile=profile, **data)
