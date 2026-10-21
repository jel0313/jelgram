"""管理者機能の DB アクセス。"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import RowMapping, text
from sqlalchemy.orm import Session


def list_reports(session: Session, status: str, limit: int) -> Sequence[RowMapping]:
    sql = text("""
        select r.id, r.post_id, p.content as post_content, p.user_id as post_author_id,
               r.reporter_id, r.reason, r.status, r.created_at, r.resolved_at
        from reports r join posts p on p.id = r.post_id
        where r.status = :status
        order by r.created_at
        limit :limit
    """)
    return session.execute(sql, {"status": status, "limit": limit}).mappings().all()


def lock_report(session: Session, report_id: int) -> RowMapping | None:
    """通報を行ロックつきで取る(10-3 悲観的ロック)。

    2人の管理者が同時に同じ通報を処理しても、2人目は1人目の確定を待ち、
    その後「処理済み」を読むので二重に処理されない。
    """
    sql = text("select id, post_id, status from reports where id = :id for update")
    return session.execute(sql, {"id": report_id}).mappings().one_or_none()


def resolve_reports_for_post(
    session: Session, post_id: int, admin_id: UUID | None, status: str
) -> None:
    """同じ投稿への未処理の通報を、まとめて処理済みにする。"""
    sql = text("""
        update reports set status = :status, resolved_by = :admin, resolved_at = now()
        where post_id = :post_id and status = 'open'
    """)
    session.execute(sql, {"post_id": post_id, "admin": admin_id, "status": status})


def resolve_report(session: Session, report_id: int, admin_id: UUID, status: str) -> None:
    sql = text("""
        update reports set status = :status, resolved_by = :admin, resolved_at = now()
        where id = :id
    """)
    session.execute(sql, {"id": report_id, "admin": admin_id, "status": status})


def set_post_hidden(session: Session, post_id: int, hidden: bool) -> bool:
    sql = text(f"""
        update posts set hidden_at = {"now()" if hidden else "null"}
        where id = :id and deleted_at is null returning id
    """)
    return session.execute(sql, {"id": post_id}).one_or_none() is not None


def set_user_status(session: Session, user_id: UUID, status: str) -> bool:
    sql = text("""
        update profiles set status = :status
        where id = :id and status <> 'deleted' and role <> 'admin' returning id
    """)
    return session.execute(sql, {"id": user_id, "status": status}).one_or_none() is not None


def insert_system_report(session: Session, post_id: int, reason: str) -> None:
    """AI・外部サービスによる自動判定の通報(通報者なし)。"""
    sql = text("insert into reports (reporter_id, post_id, reason) values (null, :p, :reason)")
    session.execute(sql, {"p": post_id, "reason": reason[:500]})


def list_audit_logs(session: Session, limit: int) -> Sequence[RowMapping]:
    sql = text("""
        select id, actor_id, action, target_type, target_id, details, request_id, created_at
        from audit_logs order by created_at desc, id desc limit :limit
    """)
    return session.execute(sql, {"limit": limit}).mappings().all()
