"""管理者機能の業務ロジック(7-5)。操作はすべて監査ログに残す(15-4)。"""

from uuid import UUID

from sqlalchemy.orm import Session

from app.admin import repository
from app.admin.schemas import AuditLogResponse, ReportResponse, ReportStatus
from app.core import audit
from app.core.exceptions import ConflictError, NotFoundError
from app.posts.exceptions import PostNotFoundError
from app.users.exceptions import UserNotFoundError


class ReportNotFoundError(NotFoundError):
    code = "report_not_found"
    message = "通報が見つかりません"


class ReportAlreadyResolvedError(ConflictError):
    code = "report_already_resolved"
    message = "この通報はすでに処理されています"


def list_reports(session: Session, status: ReportStatus, limit: int) -> list[ReportResponse]:
    return [
        ReportResponse.model_validate(dict(r))
        for r in repository.list_reports(session, status, limit)
    ]


def resolve_report(session: Session, report_id: int, admin_id: UUID, action: str) -> None:
    report = repository.lock_report(session, report_id)  # ここで行ロック
    if report is None:
        raise ReportNotFoundError
    if report["status"] != "open":
        raise ReportAlreadyResolvedError

    if action == "hide_post":
        repository.set_post_hidden(session, report["post_id"], hidden=True)
        repository.resolve_reports_for_post(session, report["post_id"], admin_id, "resolved")
    else:
        repository.resolve_report(session, report_id, admin_id, "dismissed")
    audit.record(
        session,
        actor_id=admin_id,
        action=f"report.{action}",
        target_type="report",
        target_id=report_id,
        details={"post_id": report["post_id"]},
    )
    session.commit()


def set_post_hidden(session: Session, post_id: int, admin_id: UUID, hidden: bool) -> None:
    if not repository.set_post_hidden(session, post_id, hidden):
        raise PostNotFoundError
    audit.record(
        session,
        actor_id=admin_id,
        action="post.hide" if hidden else "post.unhide",
        target_type="post",
        target_id=post_id,
    )
    session.commit()


def set_user_suspended(session: Session, user_id: UUID, admin_id: UUID, suspended: bool) -> None:
    """凍結・解除。凍結中のユーザーは API を使えず(403)、投稿も見えなくなる。"""
    if not repository.set_user_status(session, user_id, "suspended" if suspended else "active"):
        raise UserNotFoundError
    audit.record(
        session,
        actor_id=admin_id,
        action="user.suspend" if suspended else "user.unsuspend",
        target_type="user",
        target_id=user_id,
    )
    session.commit()


def hide_post_automatically(session: Session, post_id: int, source: str, reason: str) -> None:
    """AI・外部サービスの判定で投稿を非表示にし、管理者の確認用に通報を作る(12-6・11-6)。

    commit は呼び出し元。
    """
    if repository.set_post_hidden(session, post_id, hidden=True):
        repository.insert_system_report(session, post_id, f"[{source}] {reason}")
        audit.record(
            session,
            actor_id=None,
            action="post.auto_hide",
            target_type="post",
            target_id=post_id,
            details={"source": source, "reason": reason},
        )


def list_audit_logs(session: Session, limit: int) -> list[AuditLogResponse]:
    return [
        AuditLogResponse.model_validate(dict(r)) for r in repository.list_audit_logs(session, limit)
    ]
