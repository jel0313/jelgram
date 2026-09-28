"""認証の入出力の形。"""

from uuid import UUID

from pydantic import BaseModel


class CurrentUser(BaseModel):
    """ログイン中のユーザー。"""

    id: UUID
    email: str | None = None
