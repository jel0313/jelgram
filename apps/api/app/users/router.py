"""ユーザー・フォロー・ブロック・自分のアカウントの API。

URL 設計(16-1):
    /me ……………………………… 自分(ログイン中のユーザー)
    /users/{username} ……… ほかの人(id ではなくユーザー名で指定する。URL が読みやすい)
    /users/{username}/followers ・ /following ・ /posts ・ /follow ・ /block
"""

from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, File, Path, Query, UploadFile, status

from app.auth.dependencies import CurrentUserDep, rate_limit
from app.core.clock import NowDep
from app.core.config import SettingsDep
from app.core.db import DbSessionDep
from app.core.email import send_email
from app.core.redis import RedisDep
from app.core.schemas import COMMON_ERROR_RESPONSES, ErrorResponse, OffsetPage
from app.media.constants import MAX_IMAGE_BYTES
from app.media.storage import StorageDep
from app.posts import service as posts_service
from app.posts.schemas import Author, PostResponse, PostSort
from app.users import service
from app.users.schemas import (
    AccountExport,
    FollowRequest,
    FollowResponse,
    MeResponse,
    ProfileUpdate,
    UserProfile,
    UserSearchResult,
)

router = APIRouter(tags=["users"], responses=COMMON_ERROR_RESPONSES)

Username = Annotated[str, Path(pattern=r"^[A-Za-z0-9_]{3,30}$", examples=["hanako_01"])]
NOT_FOUND: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse, "description": "ユーザーがいない"}
}
_follow_limit = Depends(rate_limit("follows", "rate_limit_follows_per_minute"))


# ---------------------------------------------------------------- 自分


@router.get("/me", response_model=MeResponse)
def get_me(
    user: CurrentUserDep, session: DbSessionDep, storage: StorageDep, settings: SettingsDep
) -> MeResponse:
    """ログイン中のユーザー(メールアドレスなど、本人にだけ見せる項目を含む)。"""
    return service.get_me(session, storage, user.id, settings.media_signed_url_expires_seconds)


@router.patch(
    "/me/profile",
    response_model=MeResponse,
    responses={409: {"model": ErrorResponse, "description": "ユーザー名が使われている"}},
)
def update_profile(
    body: ProfileUpdate,
    user: CurrentUserDep,
    session: DbSessionDep,
    redis: RedisDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> MeResponse:
    """プロフィールを変更する(送った項目だけ)。非公開をやめると、承認待ちは全部承認される。"""
    return service.update_profile(
        session, redis, storage, user.id, body, settings.media_signed_url_expires_seconds
    )


@router.put(
    "/me/avatar",
    response_model=MeResponse,
    dependencies=[Depends(rate_limit("uploads", "rate_limit_uploads_per_minute"))],
)
def update_avatar(
    file: Annotated[UploadFile, File(description="画像(5MB まで)")],
    user: CurrentUserDep,
    session: DbSessionDep,
    redis: RedisDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> MeResponse:
    """プロフィール画像を差し替える(9-9)。古い画像は自動で消える。"""
    return service.update_avatar(
        session,
        redis,
        storage,
        user.id,
        data=file.file.read(MAX_IMAGE_BYTES + 1),
        filename=file.filename,
        content_type=file.content_type,
        expires_in=settings.media_signed_url_expires_seconds,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(user: CurrentUserDep, session: DbSessionDep, redis: RedisDep) -> None:
    """退会する(21-2)。投稿・いいね・フォローなどは消え、プロフィールは匿名化される。"""
    service.delete_account(session, redis, user.id)


@router.get("/me/export", response_model=AccountExport)
def export_account(user: CurrentUserDep, session: DbSessionDep, now: NowDep) -> AccountExport:
    """自分のデータをまとめて取得する(21-3)。"""
    return service.export_account(session, user.id, now)


@router.get("/me/follow-requests", response_model=list[FollowRequest])
def list_follow_requests(user: CurrentUserDep, session: DbSessionDep) -> list[FollowRequest]:
    """自分に届いたフォローリクエスト(非公開アカウント用)。"""
    return service.list_follow_requests(session, user.id)


@router.post(
    "/me/follow-requests/{follower_id}/approve",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
def approve_follow_request(
    follower_id: UUID, user: CurrentUserDep, session: DbSessionDep, redis: RedisDep
) -> None:
    service.answer_follow_request(session, redis, user.id, follower_id, approve=True)


@router.delete(
    "/me/follow-requests/{follower_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}},
)
def reject_follow_request(
    follower_id: UUID, user: CurrentUserDep, session: DbSessionDep, redis: RedisDep
) -> None:
    service.answer_follow_request(session, redis, user.id, follower_id, approve=False)


@router.get("/me/blocks", response_model=list[Author])
def list_blocks(user: CurrentUserDep, session: DbSessionDep) -> list[Author]:
    return service.list_blocks(session, user.id)


# ---------------------------------------------------------------- ほかの人


@router.get("/users/search", response_model=list[UserSearchResult])
def search_users(
    q: Annotated[str, Query(min_length=1, max_length=50)],
    user: CurrentUserDep,
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> list[UserSearchResult]:
    """ユーザー名・表示名で検索する(4-3)。"""
    return service.search_users(session, user.id, q, limit)


@router.get("/users/{username}", response_model=UserProfile, responses=NOT_FOUND)
def get_profile(
    username: Username,
    user: CurrentUserDep,
    session: DbSessionDep,
    redis: RedisDep,
    storage: StorageDep,
    settings: SettingsDep,
) -> UserProfile:
    """プロフィールを取得する(1-1 パスパラメータ)。"""
    return service.get_profile(
        session, redis, storage, username, user.id, settings.media_signed_url_expires_seconds
    )


@router.get("/users/{username}/posts", response_model=OffsetPage[PostResponse], responses=NOT_FOUND)
def get_user_posts(
    username: Username,
    user: CurrentUserDep,
    session: DbSessionDep,
    storage: StorageDep,
    settings: SettingsDep,
    sort: Annotated[PostSort, Query(description="new:新しい順 / likes:いいね数順")] = "new",
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0, le=10_000)] = 0,
) -> OffsetPage[PostResponse]:
    """ユーザーの投稿一覧(4-1・4-4)。非公開アカウントは、承認済みフォロワーにだけ見える。"""
    author_id = service.resolve_username(session, username, user.id)
    return posts_service.get_user_posts(
        session,
        storage,
        user.id,
        author_id,
        sort,
        limit,
        offset,
        settings.media_signed_url_expires_seconds,
    )


def _follow_list(direction: Literal["followers", "following"]):  # type: ignore[no-untyped-def]
    def endpoint(
        username: Username,
        user: CurrentUserDep,
        session: DbSessionDep,
        limit: Annotated[int, Query(ge=1, le=100)] = 50,
        offset: Annotated[int, Query(ge=0)] = 0,
    ) -> OffsetPage[Author]:
        return service.list_follow_users(session, user.id, username, direction, limit, offset)

    endpoint.__doc__ = "フォロワーの一覧" if direction == "followers" else "フォロー中の一覧"
    return endpoint


router.add_api_route(
    "/users/{username}/followers",
    _follow_list("followers"),
    methods=["GET"],
    response_model=OffsetPage[Author],
    responses=NOT_FOUND,
    name="list_followers",
)
router.add_api_route(
    "/users/{username}/following",
    _follow_list("following"),
    methods=["GET"],
    response_model=OffsetPage[Author],
    responses=NOT_FOUND,
    name="list_following",
)


@router.post(
    "/users/{username}/follow",
    response_model=FollowResponse,
    dependencies=[_follow_limit],
    responses=NOT_FOUND,
)
def follow(
    username: Username,
    user: CurrentUserDep,
    session: DbSessionDep,
    redis: RedisDep,
    settings: SettingsDep,
    background_tasks: BackgroundTasks,
) -> FollowResponse:
    """フォローする。非公開アカウントなら承認待ち(pending)になる。

    相手へのメールは、応答を返した後に送る(BackgroundTasks。11-3)。
    """
    response, email = service.follow(session, redis, user.id, username)
    if email is not None:
        background_tasks.add_task(
            send_email, settings, to=email.to, subject=email.subject, body=email.body
        )
    return response


@router.delete(
    "/users/{username}/follow",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[_follow_limit],
    responses=NOT_FOUND,
)
def unfollow(
    username: Username, user: CurrentUserDep, session: DbSessionDep, redis: RedisDep
) -> None:
    """フォローをやめる(承認待ちの取り消しも)。"""
    service.unfollow(session, redis, user.id, username)


@router.post("/users/{username}/block", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND)
def block(username: Username, user: CurrentUserDep, session: DbSessionDep, redis: RedisDep) -> None:
    """ブロックする(7-4)。お互いのフォローは外れ、お互いの投稿・コメントが見えなくなる。"""
    service.block(session, redis, user.id, username)


@router.delete(
    "/users/{username}/block", status_code=status.HTTP_204_NO_CONTENT, responses=NOT_FOUND
)
def unblock(
    username: Username, user: CurrentUserDep, session: DbSessionDep, redis: RedisDep
) -> None:
    service.unblock(session, redis, user.id, username)
