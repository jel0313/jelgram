"""例外ハンドラー(5-2〜5-4)。どの例外も {"code", "message", "details"} の形で返す。"""

import logging
from collections.abc import Mapping

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError

logger = logging.getLogger(__name__)


def _error(
    status: int,
    code: str,
    message: str,
    details: object = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        {"code": code, "message": message, "details": details},
        status_code=status,
        headers=headers,
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """アプリの例外(AppError とその子)。"""
    if exc.status_code >= 500:
        logger.error("アプリのエラー", extra={"code": exc.code})
    return _error(exc.status_code, exc.code, exc.message, exc.details, exc.headers)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """入力の検証エラー(422)。

    FastAPI の標準の形は `input`(送られた値そのもの)を含む。
    パスワードなどがエラー応答やログにそのまま出ないよう、項目・理由だけを返す(5-4)。
    """
    details = [
        {
            "field": ".".join(str(part) for part in error["loc"]),
            "message": error["msg"],
            "type": error["type"],
        }
        for error in exc.errors()
    ]
    return _error(422, "validation_error", "入力内容に誤りがあります", details)


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Starlette の HTTPException(存在しない URL の 404・405 など)。"""
    messages = {404: "見つかりません", 405: "このメソッドは使えません"}
    return _error(
        exc.status_code,
        f"http_{exc.status_code}",
        messages.get(exc.status_code, str(exc.detail)),
        headers=exc.headers,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
