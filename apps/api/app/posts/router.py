"""投稿・いいねの API。

パス・クエリ・ボディの使い分け(1-1):
- パス   :どのリソースか(/posts/{post_id})
- クエリ :一覧の絞り込み・並び順・ページ(?limit=20&cursor=...)
- ボディ :作る・変える中身(投稿の本文など)
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Path, Query, status

from app.auth.dependencies import CurrentUserDep, rate_limit
from app.core.clock import NowDep
from app.core.config import SettingsDep
from app.core.db import DbSessionDep
from app.core.redis import RedisDep
from app.core.schemas import COMMON_ERROR_RESPONSES, CursorPage, ErrorResponse
from app.media.storage import StorageDep
from app.posts import service
from app.posts.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE
from app.posts.schemas import (
    LikeResponse,
    PostCreate,
    PostPatch,
    PostReplace,
    PostResponse,
    ReportCreate,
)

router = APIRouter(tags=["posts"], responses=COMMON_ERROR_RESPONSES)

Limit = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE, description="1ページの件数")]
Cursor = Annotated[str | None, Query(description="前のページの next_cursor")]
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "投稿がない・見る権限がない"}
}


@router.get("/posts", response_model=CursorPage[PostResponse])
def get_timeline(
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
    cursor: Cursor = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
) -> CursorPage[PostResponse]:
    """全体のタイムライン(見てよい投稿を新しい順に)。"""
    return service.get_timeline(
        session, storage, user.id, cursor, limit, settings.media_signed_url_expires_seconds
    )


@router.get("/feed", response_model=CursorPage[PostResponse])
def get_feed(
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
    cursor: Cursor = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
) -> CursorPage[PostResponse]:
    """フォロー中の人と自分の投稿を新しい順に(4-2)。"""
    return service.get_feed(
        session, storage, user.id, cursor, limit, settings.media_signed_url_expires_seconds
    )


@router.get("/posts/popular", response_model=list[PostResponse])
def get_popular_posts(
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    redis: RedisDep,
    settings: SettingsDep,
    now: NowDep,
) -> list[PostResponse]:
    """最近 7 日間の人気投稿(いいね数順。公開アカウントのみ)。"""
    return service.get_popular_posts(
        session, storage, redis, user.id, now, settings.media_signed_url_expires_seconds
    )


@router.get("/posts/search", response_model=list[PostResponse])
def search_posts(
    q: Annotated[str, Query(min_length=1, max_length=100, description="検索語(部分一致)")],
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
    limit: Limit = DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0, le=1000)] = 0,
) -> list[PostResponse]:
    """本文で投稿を検索する(21-7)。"""
    return service.search_posts(
        session, storage, user.id, q, limit, offset, settings.media_signed_url_expires_seconds
    )


@router.get("/hashtags/{tag}/posts", response_model=CursorPage[PostResponse])
def get_hashtag_posts(
    tag: Annotated[str, Path(min_length=1, max_length=51)],
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
    cursor: Cursor = None,
    limit: Limit = DEFAULT_PAGE_SIZE,
) -> CursorPage[PostResponse]:
    """ハッシュタグが付いた投稿を新しい順に(4-3)。"""
    return service.get_hashtag_posts(
        session, storage, user.id, tag, cursor, limit, settings.media_signed_url_expires_seconds
    )


@router.get("/posts/{post_id}", response_model=PostResponse, responses=NOT_FOUND)
def get_post(
    post_id: int,
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> PostResponse:
    """投稿を1件取得する(3-2)。"""
    return service.get_post(
        session, storage, post_id, user.id, settings.media_signed_url_expires_seconds
    )


@router.post(
    "/posts",
    response_model=PostResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("posts", "rate_limit_posts_per_minute"))],
    responses={
        400: {"model": ErrorResponse, "description": "禁止語・使えない画像"},
        429: {"model": ErrorResponse, "description": "投稿しすぎ"},
    },
)
def create_post(
    body: PostCreate,
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
    idempotency_key: Annotated[
        str | None,
        Header(max_length=255, description="二重投稿を防ぐキー(操作ごとに新しい UUID)"),
    ] = None,
) -> PostResponse:
    """投稿する(3-1)。同じ Idempotency-Key で再送しても、投稿は1つだけ(10-4)。"""
    return service.create_post(
        session, storage, user.id, body, settings.media_signed_url_expires_seconds, idempotency_key
    )


@router.put(
    "/posts/{post_id}",
    response_model=PostResponse,
    responses={**NOT_FOUND, 403: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def replace_post(
    post_id: int,
    body: PostReplace,
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> PostResponse:
    """投稿を編集する(PUT:編集できる項目を全部送る)。"""
    return service.update_post(
        session, storage, post_id, user.id, body, settings.media_signed_url_expires_seconds
    )


@router.patch(
    "/posts/{post_id}",
    response_model=PostResponse,
    responses={**NOT_FOUND, 403: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def patch_post(
    post_id: int,
    body: PostPatch,
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> PostResponse:
    """投稿を編集する(PATCH:変えたい項目だけ送る)。"""
    return service.update_post(
        session, storage, post_id, user.id, body, settings.media_signed_url_expires_seconds
    )


@router.delete(
    "/posts/{post_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={**NOT_FOUND, 403: {"model": ErrorResponse}},
)
def delete_post(post_id: int, user: CurrentUserDep, session: DbSessionDep, redis: RedisDep) -> None:
    """投稿を削除する(自分の投稿だけ)。"""
    service.delete_post(session, redis, post_id, user.id)


_like_limit = Depends(rate_limit("likes", "rate_limit_likes_per_minute"))


@router.post(
    "/posts/{post_id}/like",
    response_model=LikeResponse,
    dependencies=[_like_limit],
    responses=NOT_FOUND,
)
def like_post(post_id: int, user: CurrentUserDep, session: DbSessionDep) -> LikeResponse:
    """いいねする。いいね済みでも 200(結果は同じ)。"""
    return service.like_post(session, post_id, user.id)


@router.delete(
    "/posts/{post_id}/like",
    response_model=LikeResponse,
    dependencies=[_like_limit],
    responses=NOT_FOUND,
)
def unlike_post(post_id: int, user: CurrentUserDep, session: DbSessionDep) -> LikeResponse:
    """いいねを取り消す。"""
    return service.unlike_post(session, post_id, user.id)


@router.post(
    "/posts/{post_id}/report",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit("reports", "rate_limit_reports_per_minute"))],
    responses=NOT_FOUND,
)
def report_post(
    post_id: int, body: ReportCreate, user: CurrentUserDep, session: DbSessionDep
) -> None:
    """投稿を通報する(7-5)。"""
    service.report_post(session, post_id, user.id, body.reason)
