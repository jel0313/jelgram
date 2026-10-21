"""通知の業務ロジック(11-2)。

いいね・コメント・フォローの service から `notify()` を呼ぶ。
通知の行と「プッシュ通知を送る」Outbox イベントを、呼び出し元と同じトランザクションで書く(20-4)。
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.core import outbox
from app.core.schemas import CursorPage, decode_cursor, encode_cursor
from app.notifications import repository
from app.notifications.schemas import NotificationResponse, UnreadCountResponse
from app.posts.schemas import Author

NotificationType = Literal["like", "comment", "follow", "follow_request", "follow_accepted"]


def notify(
    session: Session,
    *,
    recipient_id: UUID,
    actor_id: UUID,
    type_: NotificationType,
    post_id: int | None = None,
    comment_id: int | None = None,
) -> None:
    """通知を作る(commit は呼び出し元)。

    自分への通知・ブロック関係にある相手からの通知は作らない。
    """
    if recipient_id == actor_id:
        return
    if repository.is_blocked_either_way(session, recipient_id, actor_id):
        return
    notification_id = repository.insert_notification(
        session,
        recipient_id=recipient_id,
        actor_id=actor_id,
        type_=type_,
        post_id=post_id,
        comment_id=comment_id,
    )
    outbox.enqueue(session, outbox.NOTIFICATION_CREATED, {"notification_id": notification_id})


def list_notifications(
    session: Session, user_id: UUID, cursor: str | None, limit: int
) -> CursorPage[NotificationResponse]:
    decoded = decode_cursor(cursor) if cursor else None
    rows = repository.list_notifications(session, user_id, decoded, limit)
    has_next = len(rows) > limit
    rows = rows[:limit]
    items = [
        NotificationResponse(
            id=row["id"],
            type=row["type"],
            actor=Author(
                id=row["actor_id"],
                username=row["actor_username"],
                display_name=row["actor_display_name"],
                avatar_url=row["actor_avatar_url"],
            ),
            post_id=row["post_id"],
            comment_id=row["comment_id"],
            read=row["read_at"] is not None,
            created_at=row["created_at"],
        )
        for row in rows
    ]
    next_cursor = encode_cursor(rows[-1]["created_at"], rows[-1]["id"]) if has_next else None
    return CursorPage(items=items, next_cursor=next_cursor)


def mark_read(session: Session, user_id: UUID, ids: list[int] | None, now: datetime) -> None:
    """既読にする。ids を省略したら全部。"""
    repository.mark_read(session, user_id, ids, now)
    session.commit()


def unread_count(session: Session, user_id: UUID) -> UnreadCountResponse:
    return UnreadCountResponse(unread=repository.count_unread(session, user_id))
