"""構造化ログ(JSON)とマスク(15-1・15-5)。

1行 = 1つの JSON。request_id が全部のログに付くので、1回のリクエストのログをまとめて追える。

    {"time": "...", "level": "INFO", "logger": "app.access", "message": "access",
     "request_id": "3f2a...", "method": "GET", "path": "/api/v1/posts", "status": 200, ...}
"""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

# 今処理しているリクエストの ID。ミドルウェアがセットし、ログが読む
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

# LogRecord に最初からある属性。これ以外を extra(追加の項目)として出力する
_RESERVED = set(logging.makeLogRecord({}).__dict__) | {"message", "asctime"}

# 値を伏せるキー(大文字小文字を区別しない部分一致)
_SENSITIVE_KEYS = ("password", "token", "secret", "authorization", "api_key", "apikey", "cookie")

# 文章の中から伏せる値
_MASK_PATTERNS = [
    (re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+"), "Bearer ***"),
    (re.compile(r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+"), "***JWT***"),
    (re.compile(r"sb_(secret|publishable)_[A-Za-z0-9_-]+"), "sb_***"),
    (re.compile(r"AIza[0-9A-Za-z_-]{20,}"), "AIza***"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "***@***"),  # メールアドレス(個人情報)
]


def mask_text(text: str) -> str:
    """文章の中のトークン・API キー・メールアドレスを伏せる。"""
    for pattern, replacement in _MASK_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def mask_value(key: str, value: Any) -> Any:
    """キー名が秘密っぽければ値ごと伏せる。dict・list は中まで見る。"""
    if any(s in key.lower() for s in _SENSITIVE_KEYS):
        return "***"
    if isinstance(value, dict):
        return {k: mask_value(str(k), v) for k, v in value.items()}
    if isinstance(value, list):
        return [mask_value(key, v) for v in value]
    if isinstance(value, str):
        return mask_text(value)
    return value


class JsonFormatter(logging.Formatter):
    """ログを1行の JSON にする。"""

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "time": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": mask_text(record.getMessage()),
            "request_id": request_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                data[key] = mask_value(key, value)
        if record.exc_info:
            data["exception"] = mask_text(self.formatException(record.exc_info))
        return json.dumps(data, ensure_ascii=False, default=str)


class TextFormatter(logging.Formatter):
    """開発中に読みやすい1行の形式(LOG_JSON=false のとき)。"""

    def format(self, record: logging.LogRecord) -> str:
        extras = {
            k: mask_value(k, v)
            for k, v in record.__dict__.items()
            if k not in _RESERVED and not k.startswith("_")
        }
        line = f"{record.levelname:<7} {record.name}: {mask_text(record.getMessage())}"
        if extras:
            line += " " + json.dumps(extras, ensure_ascii=False, default=str)
        if record.exc_info:
            line += "\n" + self.formatException(record.exc_info)
        return line


def setup_logging(level: str = "INFO", *, json_format: bool = True) -> None:
    """ルートロガーに出力先と形式を設定する。起動時に1回だけ呼ぶ。"""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_format else TextFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # アクセスログは自前のミドルウェアで出すので、Uvicorn のものは止める(二重に出さない)
    logging.getLogger("uvicorn.access").disabled = True
