"""管理者機能の入出力の形。"""

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel

ReportStatus = Literal["open", "resolved", "dismissed"]


class ReportResponse(BaseModel):
    id: int
    post_id: int
    post_content: str
    post_author_id: UUID
    reporter_id: UUID | None
    reason: str
    status: ReportStatus
    created_at: datetime
    resolved_at: datetime | None


class ResolveReportRequest(BaseModel):
    action: Literal["hide_post", "dismiss"]


class AuditLogResponse(BaseModel):
    id: int
    actor_id: UUID | None
    action: str
    target_type: str
    target_id: str
    details: dict[str, Any]
    request_id: str | None
    created_at: datetime
