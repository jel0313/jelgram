"""通知・プッシュ通知の宛先の DB アクセス。"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session


def is_blocked_either_way(session: Session, a: UUID, b: UUID) -> bool:
    sql = text("""
        select exists (
            select 1 from blocks
            where (blocker_id = :a and blocked_id = :b) or (blocker_id = :b and blocked_id = :a)
        )
    """)
    return bool(session.execute(sql, {"a": a, "b": b}).scalar_one())


def insert_notification(
    session: Session,
    *,
    recipient_id: UUID,
    actor_id: UUID,
    type_: str,
    post_id: int | None,
    comment_id: int | None,
) -> int:
    sql = text("""
        insert into notifications (recipient_id, actor_id, type, post_id, comment_id)
        values (:recipient_id, :actor_id, :type, :post_id, :comment_id)
        returning id
    """)
    notification_id: int = session.execute(
        sql,
        {
            "recipient_id": recipient_id,
            "actor_id": actor_id,
            "type": type_,
            "post_id": post_id,
            "comment_id": comment_id,
        },
    ).scalar_one()
    return notification_id


def list_notifications(
    session: Session, user_id: UUID, cursor: tuple[datetime, int] | None, limit: int
) -> Sequence[RowMapping]:
    sql = text("""
        select n.id, n.type, n.post_id, n.comment_id, n.read_at, n.created_at,
               a.id as actor_id, a.username as actor_username,
               a.display_name as actor_display_name, a.avatar_url as actor_avatar_url
        from notifications n join profiles a on a.id = n.actor_id
        where n.recipient_id = :user_id and a.status = 'active'
          and (
              cast(:cursor_t as timestamptz) is null
              or (n.created_at, n.id) < (cast(:cursor_t as timestamptz), cast(:cursor_id as bigint))
          )
        order by n.created_at desc, n.id desc
        limit :limit
    """)
    params = {
        "user_id": user_id,
        "limit": limit + 1,
        "cursor_t": cursor[0] if cursor else None,
        "cursor_id": cursor[1] if cursor else None,
    }
    return session.execute(sql, params).mappings().all()


def mark_read(session: Session, user_id: UUID, ids: list[int] | None, now: datetime) -> None:
    # 自分宛て(recipient_id = :user_id)の通知だけを更新する。
    # 他人の通知 id を送られても変わらない(7-6)
    sql = text("""
        update notifications set read_at = :now
        where recipient_id = :user_id and read_at is null
          and (cast(:ids as bigint[]) is null or id = any(cast(:ids as bigint[])))
    """)
    session.execute(sql, {"user_id": user_id, "ids": ids, "now": now})


def count_unread(session: Session, user_id: UUID) -> int:
    sql = text("select count(*) from notifications where recipient_id = :u and read_at is null")
    count: int = session.execute(sql, {"u": user_id}).scalar_one()
    return count


def get_notification(session: Session, notification_id: int) -> RowMapping | None:
    sql = text("""
        select n.id, n.type, n.recipient_id, a.display_name as actor_display_name
        from notifications n join profiles a on a.id = n.actor_id
        where n.id = :id
    """)
    return session.execute(sql, {"id": notification_id}).mappings().one_or_none()


# ---------------------------------------------------------------- プッシュ通知の宛先(11-7)


def upsert_push_subscription(
    session: Session, user_id: UUID, endpoint: str, p256dh: str, auth: str
) -> None:
    """同じ端末(endpoint)が別の人で登録し直したら、持ち主を付け替える。"""
    sql = text("""
        insert into push_subscriptions (user_id, endpoint, p256dh, auth)
        values (:user_id, :endpoint, :p256dh, :auth)
        on conflict (endpoint) do update
        set user_id = excluded.user_id, p256dh = excluded.p256dh, auth = excluded.auth
    """)
    session.execute(sql, {"user_id": user_id, "endpoint": endpoint, "p256dh": p256dh, "auth": auth})


def delete_push_subscription(session: Session, user_id: UUID, endpoint: str) -> None:
    sql = text("delete from push_subscriptions where user_id = :u and endpoint = :e")
    session.execute(sql, {"u": user_id, "e": endpoint})


def list_push_subscriptions(session: Session, user_id: UUID) -> Sequence[RowMapping]:
    sql = text("select id, endpoint, p256dh, auth from push_subscriptions where user_id = :u")
    return session.execute(sql, {"u": user_id}).mappings().all()


def delete_push_subscription_by_id(session: Session, subscription_id: int) -> None:
    session.execute(text("delete from push_subscriptions where id = :id"), {"id": subscription_id})
