"""ヘルスチェック API。"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """API が応答できるかを返す。認証不要。DB 等の外部サービスには接続しない。"""
    return HealthResponse(status="ok")
