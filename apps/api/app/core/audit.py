"""監査ログ(15-4)。管理者の操作・削除など「誰が・いつ・何をしたか」を DB に残す。

呼び出し元と同じトランザクションで書く。操作が取り消された(ロールバック)なら、記録も残らない。
"""

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.logging import mask_value, request_id_var


def record(
    session: Session,
    *,
    actor_id: UUID | None,
    action: str,
    target_type: str,
    target_id: str | int | UUID,
    details: dict[str, Any] | None = None,
) -> None:
    """監査ログを1件追加する(commit は呼び出し元)。"""
    session.execute(
        text("""
            insert into audit_logs (actor_id, action, target_type, target_id, details, request_id)
            values (:actor_id, :action, :target_type, :target_id,
                    cast(:details as jsonb), :request_id)
        """),
        {
            "actor_id": actor_id,
            "action": action,
            "target_type": target_type,
            "target_id": str(target_id),
            "details": json.dumps(mask_value("details", details or {}), ensure_ascii=False),
            "request_id": request_id_var.get(),
        },
    )
