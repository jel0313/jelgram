"""ヘルスチェックの応答の形。"""

from typing import Literal

from pydantic import BaseModel


class LiveResponse(BaseModel):
    status: Literal["ok"]


class HealthResponse(BaseModel):
    status: Literal["ok", "error"]
    checks: dict[str, Literal["ok", "error"]]
