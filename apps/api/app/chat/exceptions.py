"""AI チャットのエラー。メッセージはキャラクターの口調にする(要件定義書 3.3)。"""

from app.chat.constants import (
    AI_UNAVAILABLE_MESSAGE,
    GLOBAL_RATE_LIMIT_MESSAGE,
    RATE_LIMIT_MESSAGE,
)
from app.core.exceptions import RateLimitError, ServiceUnavailableError


class ChatRateLimitError(RateLimitError):
    code = "chat_rate_limited"
    message = RATE_LIMIT_MESSAGE


class ChatGlobalRateLimitError(RateLimitError):
    code = "chat_global_rate_limited"
    message = GLOBAL_RATE_LIMIT_MESSAGE


class AIUnavailableError(ServiceUnavailableError):
    """AI API が落ちている・時間切れ(12-7)。"""

    code = "ai_unavailable"
    message = AI_UNAVAILABLE_MESSAGE


class AIRateLimitedError(RateLimitError):
    """AI API 側の上限(無料枠)に達した。"""

    code = "ai_rate_limited"
    message = GLOBAL_RATE_LIMIT_MESSAGE
