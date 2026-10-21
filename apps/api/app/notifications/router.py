"""通知の API(11-2・11-7)。"""

from typing import Annotated

from fastapi import APIRouter, Query, status

from app.auth.dependencies import CurrentUserDep
from app.core.clock import NowDep
from app.core.db import DbSessionDep
from app.core.schemas import COMMON_ERROR_RESPONSES, CursorPage
from app.notifications import repository, service
from app.notifications.schemas import (
    MarkReadRequest,
    NotificationResponse,
    PushSubscriptionCreate,
    PushSubscriptionDelete,
    UnreadCountResponse,
)

router = APIRouter(tags=["notifications"], responses=COMMON_ERROR_RESPONSES)


@router.get("/notifications", response_model=CursorPage[NotificationResponse])
def list_notifications(
    user: CurrentUserDep,
    session: DbSessionDep,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
) -> CursorPage[NotificationResponse]:
    """自分宛ての通知を新しい順に返す。"""
    return service.list_notifications(session, user.id, cursor, limit)


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
def unread_count(user: CurrentUserDep, session: DbSessionDep) -> UnreadCountResponse:
    return service.unread_count(session, user.id)


@router.post("/notifications/read", status_code=status.HTTP_204_NO_CONTENT)
def mark_read(
    body: MarkReadRequest, user: CurrentUserDep, session: DbSessionDep, now: NowDep
) -> None:
    """通知を既読にする。"""
    service.mark_read(session, user.id, body.ids, now)


@router.post("/me/push-subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def subscribe_push(
    body: PushSubscriptionCreate, user: CurrentUserDep, session: DbSessionDep
) -> None:
    """この端末にプッシュ通知を送れるよう登録する(11-7)。"""
    repository.upsert_push_subscription(
        session, user.id, str(body.endpoint), body.keys.p256dh, body.keys.auth
    )
    session.commit()


@router.delete("/me/push-subscriptions", status_code=status.HTTP_204_NO_CONTENT)
def unsubscribe_push(
    body: PushSubscriptionDelete, user: CurrentUserDep, session: DbSessionDep
) -> None:
    repository.delete_push_subscription(session, user.id, str(body.endpoint))
    session.commit()
