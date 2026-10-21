"""全機能で使う入出力の形(エラー・ページング)。"""

import base64
import json
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.exceptions import BadRequestError


class ErrorResponse(BaseModel):
    """エラーレスポンスの共通の形(5-3)。"""

    code: str = Field(examples=["post_not_found"])
    message: str = Field(examples=["投稿が見つかりません"])
    details: Any = None


class CursorPage[T](BaseModel):
    """カーソル方式のページ(4-2)。次のページは next_cursor を渡して取る。"""

    items: list[T]
    next_cursor: str | None = Field(
        description="次のページのカーソル。null なら最後のページ", examples=[None]
    )


class OffsetPage[T](BaseModel):
    """limit / offset 方式のページ(4-1)。総件数つき。"""

    items: list[T]
    total: int
    limit: int
    offset: int


# よく使うエラーを OpenAPI に載せるための定義(16-3)
COMMON_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorResponse, "description": "未認証・トークンが無効"},
    422: {"model": ErrorResponse, "description": "入力の検証エラー"},
}


def encode_cursor(created_at: datetime, id_: int) -> str:
    """(作成日時, id) をカーソル文字列にする。中身はクライアントが解釈しない前提。"""
    raw = json.dumps({"t": created_at.isoformat(), "i": id_}).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> tuple[datetime, int]:
    """カーソル文字列を (作成日時, id) に戻す。壊れていれば 400。"""
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        data = json.loads(base64.urlsafe_b64decode(padded))
        return datetime.fromisoformat(data["t"]), int(data["i"])
    except (ValueError, KeyError, TypeError) as e:
        raise BadRequestError("カーソルが正しくありません", details={"cursor": cursor}) from e
