"""AI チャットの業務ロジック(12章)。

    ① 準備(prepare):投稿の確認 → 禁止語 → レート制限 → 質問を保存して commit
    ② AI に送る:履歴を件数・文字数で切って送る
    ③ 応答を検証して保存
① で commit してから ② に進む。AI の応答待ち(数秒)の間、トランザクションとロックを持ち続けないため。
"""

import logging
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi.sse import ServerSentEvent
from sqlalchemy.orm import Session

from app.chat import repository
from app.chat.ai_client import AIClient, AIMessage, AIResult
from app.chat.constants import HISTORY_MAX_MESSAGES, SYSTEM_PROMPT
from app.chat.exceptions import ChatGlobalRateLimitError, ChatRateLimitError
from app.chat.prompt import build_messages, validate_reply
from app.chat.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSession,
    ChatUsage,
    StreamDelta,
    StreamDone,
    StreamError,
)
from app.core.config import Settings
from app.core.exceptions import AppError
from app.moderation.service import find_blocked_words
from app.posts.exceptions import ContentNotAllowedError, PostNotFoundError

logger = logging.getLogger(__name__)

JST = ZoneInfo("Asia/Tokyo")
PACIFIC = ZoneInfo("America/Los_Angeles")  # Gemini の日次の上限がリセットされる時刻(要件定義書 4.2)


def start_of_day(now: datetime, tz: ZoneInfo) -> datetime:
    """そのタイムゾーンでの「今日の0時」を返す(UTC のまま比較できる)。"""
    local = now.astimezone(tz)
    return local.replace(hour=0, minute=0, second=0, microsecond=0)


def check_rate_limit(session: Session, user_id: UUID, now: datetime, settings: Settings) -> None:
    """DB の送信記録を数えて、上限を超えていれば 429(要件定義書 4.2)。"""
    minute_ago = now - timedelta(minutes=1)
    if (
        repository.count_user_messages(session, user_id, minute_ago)
        >= settings.rate_limit_per_user_per_minute
    ):
        raise ChatRateLimitError(retry_after=60)
    if (
        repository.count_user_messages(session, user_id, start_of_day(now, JST))
        >= settings.rate_limit_per_user_per_day
    ):
        raise ChatRateLimitError(retry_after=_seconds_until_tomorrow(now, JST))
    if repository.count_all_messages(session, minute_ago) >= settings.rate_limit_global_per_minute:
        raise ChatGlobalRateLimitError(retry_after=60)
    if (
        repository.count_all_messages(session, start_of_day(now, PACIFIC))
        >= settings.rate_limit_global_per_day
    ):
        raise ChatGlobalRateLimitError(retry_after=_seconds_until_tomorrow(now, PACIFIC))


def _seconds_until_tomorrow(now: datetime, tz: ZoneInfo) -> int:
    tomorrow = start_of_day(now, tz) + timedelta(days=1)
    return max(int((tomorrow - now).total_seconds()), 1)


@dataclass
class PreparedChat:
    user_id: UUID
    session_id: str
    post_id: int | None
    messages: list[AIMessage]


def prepare(
    session: Session, user_id: UUID, body: ChatRequest, now: datetime, settings: Settings
) -> PreparedChat:
    """① 準備。ここで出た例外は、通常の HTTP エラー(400・404・429)になる。"""
    post = None
    if body.post_id is not None:
        post = repository.get_visible_post(session, body.post_id, user_id)
        if post is None:
            raise PostNotFoundError
    if find_blocked_words(body.message):
        raise ContentNotAllowedError

    repository.lock_user(session, user_id)
    check_rate_limit(session, user_id, now, settings)
    repository.insert_message(
        session,
        user_id=user_id,
        session_id=body.session_id,
        role="user",
        content=body.message,
        post_id=body.post_id,
        now=now,
    )
    session.commit()  # ロックもここで外れる

    history = repository.get_history(session, user_id, body.session_id, HISTORY_MAX_MESSAGES)
    return PreparedChat(
        user_id=user_id,
        session_id=body.session_id,
        post_id=body.post_id,
        messages=build_messages(history, post),
    )


def _save_reply(
    session: Session, prepared: PreparedChat, result: AIResult, now: datetime
) -> ChatMessage:
    """③ 応答を検証して保存する。トークン数も記録する(12-4)。"""
    text, replaced = validate_reply(result.text, blocked=result.blocked)
    if replaced:
        logger.warning("AI の応答を差し替えました", extra={"session_id": prepared.session_id})
    row = repository.insert_message(
        session,
        user_id=prepared.user_id,
        session_id=prepared.session_id,
        role="assistant",
        content=text,
        post_id=prepared.post_id,
        now=now,
        prompt_tokens=result.prompt_tokens,
        completion_tokens=result.completion_tokens,
    )
    session.commit()
    return ChatMessage.model_validate(dict(row))


def reply(session: Session, ai: AIClient, prepared: PreparedChat, now: datetime) -> ChatResponse:
    """② ③ まとめて応答を返す。AI が落ちていたら 503(キャラクターの口調。12-7)。"""
    result = ai.generate(SYSTEM_PROMPT, prepared.messages)
    message = _save_reply(session, prepared, result, now)
    return ChatResponse(session_id=prepared.session_id, reply=message)


def reply_stream(
    session: Session, ai: AIClient, prepared: PreparedChat, now: datetime
) -> Iterator[ServerSentEvent]:
    """② ③ をストリーミングで(12-3)。

        event: delta  data: {"text": "..."}     … 届いた分ずつ
        event: done   data: {"reply": {...}}     … 最後に保存した応答
        event: error  data: {"code", "message"}  … 途中で失敗したとき

    応答の開始後は HTTP のステータスを変えられないので、エラーも event で伝える。
    """
    try:
        for chunk in ai.stream(SYSTEM_PROMPT, prepared.messages):
            if chunk.result is not None:
                message = _save_reply(session, prepared, chunk.result, now)
                yield ServerSentEvent(event="done", data=StreamDone(reply=message))
            elif chunk.text:
                yield ServerSentEvent(event="delta", data=StreamDelta(text=chunk.text))
    except AppError as e:
        yield ServerSentEvent(event="error", data=StreamError(code=e.code, message=e.message))


def get_history(session: Session, user_id: UUID, session_id: str, limit: int) -> list[ChatMessage]:
    rows = repository.get_history(session, user_id, session_id, limit)
    return [ChatMessage.model_validate(dict(row)) for row in rows]


def list_sessions(session: Session, user_id: UUID, limit: int) -> list[ChatSession]:
    return [
        ChatSession.model_validate(dict(row))
        for row in repository.list_sessions(session, user_id, limit)
    ]


def get_usage(session: Session, user_id: UUID, now: datetime, settings: Settings) -> ChatUsage:
    row = repository.usage_since(session, user_id, start_of_day(now, JST))
    return ChatUsage(
        used_today=row["used"],
        limit_per_day=settings.rate_limit_per_user_per_day,
        prompt_tokens_today=row["prompt_tokens"],
        completion_tokens_today=row["completion_tokens"],
    )
