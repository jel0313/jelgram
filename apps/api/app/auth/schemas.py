"""認証の入出力の形。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

Role = Literal["user", "admin"]


class CurrentUser(BaseModel):
    """ログイン中のユーザー(JWT と DB から作る。レスポンスには使わない)。"""

    id: UUID
    email: str | None = None
    role: Role = "user"
    session_id: str | None = None
    expires_at: datetime | None = None
