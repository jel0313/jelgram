"""ヘルスチェック API(0-4)。認証不要。

- /health/live :プロセスが応答できるか。外部サービスは見ない(落ちていたら再起動の判断に使う)
- /health      :DB・Redis にもつながるか。つながらなければ 503(負荷分散から外す判断に使う)
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from redis import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.db import DbSessionDep
from app.core.redis import RedisDep
from app.health.schemas import HealthResponse, LiveResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health/live", response_model=LiveResponse)
def live() -> LiveResponse:
    return LiveResponse(status="ok")


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": HealthResponse, "description": "DB か Redis につながらない"}},
)
def health(session: DbSessionDep, redis: RedisDep) -> HealthResponse | JSONResponse:
    """DB と Redis への接続を確かめる。Render の定期実行で、Supabase の一時停止対策も兼ねる。"""
    checks: dict[str, str] = {}
    try:
        session.execute(text("select 1"))
        checks["db"] = "ok"
    except SQLAlchemyError:
        logger.exception("ヘルスチェック:DB に接続できません")
        checks["db"] = "error"
    try:
        redis.ping()
        checks["redis"] = "ok"
    except RedisError:
        logger.warning("ヘルスチェック:Redis に接続できません")
        checks["redis"] = "error"

    if all(v == "ok" for v in checks.values()):
        return HealthResponse(status="ok", checks=checks)
    body = HealthResponse(status="error", checks=checks)
    return JSONResponse(body.model_dump(), status_code=503)
