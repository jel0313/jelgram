"""コメントの業務ロジック。

削除できる人(7-2):
    コメントを書いた人 ── 自分のコメントだから
    投稿者             ── 自分の投稿についた荒らしコメントを消せるように
編集できるのは、書いた人だけ。
"""

from collections.abc import Mapping
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.comments import repository
from app.comments.exceptions import (
    CommentNotFoundError,
    CommentsDisabledError,
    NotCommentOwnerError,
)
from app.comments.schemas import CommentCreate, CommentResponse, CommentUpdate
from app.core import audit
from app.core.schemas import CursorPage
from app.moderation.service import find_blocked_words
from app.notifications import service as notifications
from app.posts.exceptions import ContentNotAllowedError, PostNotFoundError
from app.posts.schemas import Author


def _to_response(row: Mapping[Any, Any], viewer_id: UUID) -> CommentResponse:
    return CommentResponse(
        id=row["id"],
        post_id=row["post_id"],
        content=row["content"],
        author=Author(
            id=row["author_id"],
            username=row["author_username"],
            display_name=row["author_display_name"],
            avatar_url=row["author_avatar_url"],
        ),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        can_delete=viewer_id in (row["user_id"], row["post_owner_id"]),
    )


def list_comments(
    session: Session, post_id: int, viewer_id: UUID, cursor: str | None, limit: int
) -> CursorPage[CommentResponse]:
    """コメントを古い順に返す。カーソルは最後のコメントの id。"""
    if repository.get_visible_post(session, post_id, viewer_id) is None:
        raise PostNotFoundError
    after_id = int(cursor) if cursor and cursor.isdigit() else None
    rows = repository.list_comments(session, post_id, viewer_id, after_id, limit)
    has_next = len(rows) > limit
    rows = rows[:limit]
    return CursorPage(
        items=[_to_response(row, viewer_id) for row in rows],
        next_cursor=str(rows[-1]["id"]) if has_next else None,
    )


def create_comment(
    session: Session, post_id: int, user_id: UUID, body: CommentCreate
) -> CommentResponse:
    post = repository.get_visible_post(session, post_id, user_id)
    if post is None:
        raise PostNotFoundError
    if post["comments_disabled"] and post["user_id"] != user_id:
        raise CommentsDisabledError
    if find_blocked_words(body.content):
        raise ContentNotAllowedError

    comment_id = repository.insert_comment(session, post_id, user_id, body.content)
    notifications.notify(
        session,
        recipient_id=post["user_id"],
        actor_id=user_id,
        type_="comment",
        post_id=post_id,
        comment_id=comment_id,
    )
    row = repository.get_comment(session, comment_id)
    if row is None:
        raise CommentNotFoundError
    session.commit()
    return _to_response(row, user_id)


def _get_comment_visible(session: Session, comment_id: int, viewer_id: UUID) -> Mapping[Any, Any]:
    row = repository.get_comment(session, comment_id)
    if row is None or repository.get_visible_post(session, row["post_id"], viewer_id) is None:
        raise CommentNotFoundError
    return row


def update_comment(
    session: Session, comment_id: int, user_id: UUID, body: CommentUpdate
) -> CommentResponse:
    row = _get_comment_visible(session, comment_id, user_id)
    if row["user_id"] != user_id:
        raise NotCommentOwnerError
    if find_blocked_words(body.content):
        raise ContentNotAllowedError
    repository.update_comment(session, comment_id, body.content)
    updated = repository.get_comment(session, comment_id)
    if updated is None:
        raise CommentNotFoundError
    session.commit()
    return _to_response(updated, user_id)


def delete_comment(session: Session, comment_id: int, user_id: UUID) -> None:
    row = _get_comment_visible(session, comment_id, user_id)
    if user_id not in (row["user_id"], row["post_owner_id"]):
        raise NotCommentOwnerError
    repository.soft_delete_comment(session, comment_id, row["post_id"])
    if row["user_id"] != user_id:
        # 他人のコメントを消したときは、後から確認できるよう記録する(15-4)
        audit.record(
            session,
            actor_id=user_id,
            action="comment.delete_by_post_owner",
            target_type="comment",
            target_id=comment_id,
        )
    session.commit()
