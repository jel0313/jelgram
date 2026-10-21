"""管理者の API(7-5)。すべて `AdminUserDep`(管理者ロールだけ通す依存関数)で守る。"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.admin import service
from app.admin.schemas import AuditLogResponse, ReportResponse, ReportStatus, ResolveReportRequest
from app.auth.dependencies import AdminUserDep
from app.core.db import DbSessionDep
from app.core.schemas import COMMON_ERROR_RESPONSES, ErrorResponse

router = APIRouter(
    prefix="/admin",
    tags=["admin"],
    responses={
        **COMMON_ERROR_RESPONSES,
        403: {"model": ErrorResponse, "description": "管理者ではない"},
    },
)


@router.get("/reports", response_model=list[ReportResponse])
def list_reports(
    admin: AdminUserDep,
    session: DbSessionDep,
    status_: Annotated[ReportStatus, Query(alias="status")] = "open",
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[ReportResponse]:
    """通報の一覧(古い順)。"""
    return service.list_reports(session, status_, limit)


@router.post(
    "/reports/{report_id}/resolve",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def resolve_report(
    report_id: int, body: ResolveReportRequest, admin: AdminUserDep, session: DbSessionDep
) -> None:
    """通報を処理する(投稿を非表示にする / 問題なしとして閉じる)。"""
    service.resolve_report(session, report_id, admin.id, body.action)


@router.post("/posts/{post_id}/hide", status_code=status.HTTP_204_NO_CONTENT)
def hide_post(post_id: int, admin: AdminUserDep, session: DbSessionDep) -> None:
    service.set_post_hidden(session, post_id, admin.id, hidden=True)


@router.post("/posts/{post_id}/unhide", status_code=status.HTTP_204_NO_CONTENT)
def unhide_post(post_id: int, admin: AdminUserDep, session: DbSessionDep) -> None:
    service.set_post_hidden(session, post_id, admin.id, hidden=False)


@router.post("/users/{user_id}/suspend", status_code=status.HTTP_204_NO_CONTENT)
def suspend_user(user_id: UUID, admin: AdminUserDep, session: DbSessionDep) -> None:
    """ユーザーを凍結する(管理者は凍結できない)。"""
    service.set_user_suspended(session, user_id, admin.id, suspended=True)


@router.post("/users/{user_id}/unsuspend", status_code=status.HTTP_204_NO_CONTENT)
def unsuspend_user(user_id: UUID, admin: AdminUserDep, session: DbSessionDep) -> None:
    service.set_user_suspended(session, user_id, admin.id, suspended=False)


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def list_audit_logs(
    admin: AdminUserDep, session: DbSessionDep, limit: Annotated[int, Query(ge=1, le=200)] = 100
) -> list[AuditLogResponse]:
    """監査ログ(新しい順。15-4)。"""
    return service.list_audit_logs(session, limit)
