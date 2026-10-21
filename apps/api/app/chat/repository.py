"""AI チャットの DB アクセス。"""

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session

from app.core.visibility import can_view_content_of, post_is_alive


def lock_user(session: Session, user_id: UUID) -> None:
    """同じユーザーの同時送信を1つずつ処理する(トランザクションが終わるまで有効なロック)。

    これがないと、2つ同時に送られたとき、両方が「まだ上限前」と判断して上限を超えられる。
    """
    session.execute(
        text("select pg_advisory_xact_lock(hashtext(cast(:u as text)))"), {"u": user_id}
    )


def count_user_messages(session: Session, user_id: UUID, since: datetime) -> int:
    """このユーザーが since 以降に送った回数(レート制限。要件定義書 4.2)。"""
    count: int = session.execute(
        text("""
            select count(*) from chat_messages
            where user_id = :u and role = 'user' and created_at >= :since
        """),
        {"u": user_id, "since": since},
    ).scalar_one()
    return count


def count_all_messages(session: Session, since: datetime) -> int:
    """アプリ全体で since 以降に送られた回数。"""
    count: int = session.execute(
        text("select count(*) from chat_messages where role = 'user' and created_at >= :since"),
        {"since": since},
    ).scalar_one()
    return count


def get_visible_post(session: Session, post_id: int, viewer_id: UUID) -> RowMapping | None:
    sql = text(f"""
        select p.id, p.content, a.display_name as author_display_name
        from posts p join profiles a on a.id = p.user_id
        where p.id = :id and {post_is_alive("p")} and {can_view_content_of("a")}
    """)
    return session.execute(sql, {"id": post_id, "viewer_id": viewer_id}).mappings().one_or_none()


def insert_message(
    session: Session,
    *,
    user_id: UUID,
    session_id: str,
    role: str,
    content: str,
    post_id: int | None,
    now: datetime,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
) -> RowMapping:
    sql = text("""
        insert into chat_messages
            (user_id, session_id, role, content, post_id, created_at,
             prompt_tokens, completion_tokens)
        values (:user_id, :session_id, :role, :content, :post_id, :now, :pt, :ct)
        returning id, role, content, post_id, created_at
    """)
    return (
        session.execute(
            sql,
            {
                "user_id": user_id,
                "session_id": session_id,
                "role": role,
                "content": content,
                "post_id": post_id,
                "now": now,
                "pt": prompt_tokens,
                "ct": completion_tokens,
            },
        )
        .mappings()
        .one()
    )


def get_history(
    session: Session, user_id: UUID, session_id: str, limit: int
) -> Sequence[RowMapping]:
    """自分の会話だけを、古い順に最新 limit 件(user_id で絞る。他人の会話は読めない)。"""
    sql = text("""
        select * from (
            select id, role, content, post_id, created_at from chat_messages
            where user_id = :u and session_id = :s
            order by created_at desc, id desc
            limit :limit
        ) recent
        order by created_at, id
    """)
    return session.execute(sql, {"u": user_id, "s": session_id, "limit": limit}).mappings().all()


def list_sessions(session: Session, user_id: UUID, limit: int) -> Sequence[RowMapping]:
    sql = text("""
        select session_id,
               (array_agg(content order by created_at, id))[1] as first_message,
               max(created_at) as last_message_at,
               count(*) as message_count
        from chat_messages
        where user_id = :u
        group by session_id
        order by max(created_at) desc
        limit :limit
    """)
    return session.execute(sql, {"u": user_id, "limit": limit}).mappings().all()


def usage_since(session: Session, user_id: UUID, since: datetime) -> RowMapping:
    sql = text("""
        select count(*) filter (where role = 'user') as used,
               coalesce(sum(prompt_tokens), 0) as prompt_tokens,
               coalesce(sum(completion_tokens), 0) as completion_tokens
        from chat_messages where user_id = :u and created_at >= :since
    """)
    return session.execute(sql, {"u": user_id, "since": since}).mappings().one()
