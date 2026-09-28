"""ヘルスチェック API。"""

from fastapi import APIRouter

from app.health.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """API が応答できるかを返す。認証不要。DB 等の外部サービスには接続しない。"""
    return HealthResponse(status="ok")
