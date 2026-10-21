"""コメントの API。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status

from app.auth.dependencies import CurrentUserDep, rate_limit
from app.comments import service
from app.comments.schemas import CommentCreate, CommentResponse, CommentUpdate
from app.core.db import DbSessionDep
from app.core.schemas import COMMON_ERROR_RESPONSES, CursorPage, ErrorResponse

router = APIRouter(tags=["comments"], responses=COMMON_ERROR_RESPONSES)

ERRORS: dict[int | str, dict[str, Any]] = {
    403: {"model": ErrorResponse, "description": "権限がない・コメント不可の投稿"},
    404: {"model": ErrorResponse, "description": "ない・見る権限がない"},
}


@router.get(
    "/posts/{post_id}/comments", response_model=CursorPage[CommentResponse], responses=ERRORS
)
def list_comments(
    post_id: int,
    user: CurrentUserDep,
    session: DbSessionDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> CursorPage[CommentResponse]:
    """投稿のコメントを古い順に返す。"""
    return service.list_comments(session, post_id, user.id, cursor, limit)


@router.post(
    "/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit("comments", "rate_limit_comments_per_minute"))],
    responses=ERRORS,
)
def create_comment(
    post_id: int, body: CommentCreate, user: CurrentUserDep, session: DbSessionDep
) -> CommentResponse:
    """コメントする。"""
    return service.create_comment(session, post_id, user.id, body)


@router.patch("/comments/{comment_id}", response_model=CommentResponse, responses=ERRORS)
def update_comment(
    comment_id: int, body: CommentUpdate, user: CurrentUserDep, session: DbSessionDep
) -> CommentResponse:
    """自分のコメントを編集する。"""
    return service.update_comment(session, comment_id, user.id, body)


@router.delete("/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS)
def delete_comment(comment_id: int, user: CurrentUserDep, session: DbSessionDep) -> None:
    """コメントを削除する(自分のコメント・自分の投稿についたコメント)。"""
    service.delete_comment(session, comment_id, user.id)
