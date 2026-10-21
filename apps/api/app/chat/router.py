"""AI チャットの API(12章)。

同期の def で書いている(11-1)。DB(SQLAlchemy)も AI(httpx2.Client)も同期の部品なので、
FastAPI がスレッドプールで動かす。async def の中で同期の部品を呼ぶと、ほかの全リクエストが止まる。
"""

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.auth.dependencies import CurrentUserDep
from app.chat import service
from app.chat.ai_client import AIClientDep
from app.chat.schemas import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    ChatSession,
    ChatUsage,
    SessionId,
)
from app.core.clock import NowDep
from app.core.config import SettingsDep
from app.core.db import DbSessionDep
from app.core.schemas import COMMON_ERROR_RESPONSES, ErrorResponse

router = APIRouter(prefix="/chat", tags=["chat"], responses=COMMON_ERROR_RESPONSES)

ERRORS: dict[int | str, dict[str, Any]] = {
    400: {"model": ErrorResponse, "description": "禁止語"},
    404: {"model": ErrorResponse, "description": "post_id の投稿がない・見る権限がない"},
    429: {"model": ErrorResponse, "description": "使いすぎ(キャラクターの口調のメッセージ)"},
    503: {"model": ErrorResponse, "description": "AI が応答できない"},
}


def prepare_chat(
    body: ChatRequest,
    user: CurrentUserDep,
    session: DbSessionDep,
    now: NowDep,
    settings: SettingsDep,
) -> service.PreparedChat:
    """チェックと質問の保存。依存関数にすると、ストリーミングの開始前に実行される。

    そのため、ここでのエラー(429 など)は普通の HTTP エラーとして返せる。
    """
    return service.prepare(session, user.id, body, now, settings)


PreparedDep = Annotated[service.PreparedChat, Depends(prepare_chat)]


@router.post("", response_model=ChatResponse, responses=ERRORS)
def send_message(
    prepared: PreparedDep, ai: AIClientDep, session: DbSessionDep, now: NowDep
) -> ChatResponse:
    """AI にメッセージを送り、応答をまとめて受け取る。"""
    return service.reply(session, ai, prepared, now)


@router.post("/stream", response_class=EventSourceResponse, responses=ERRORS)
def send_message_stream(
    prepared: PreparedDep, ai: AIClientDep, session: DbSessionDep, now: NowDep
) -> Iterator[ServerSentEvent]:
    """AI の応答を、届いた分から少しずつ受け取る(Server-Sent Events。12-3)。"""
    yield from service.reply_stream(session, ai, prepared, now)


@router.get("/history", response_model=list[ChatMessage])
def get_history(
    session_id: Annotated[SessionId, Query()],
    user: CurrentUserDep,
    session: DbSessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ChatMessage]:
    """会話の履歴(自分のものだけ。古い順)。"""
    return service.get_history(session, user.id, session_id, limit)


@router.get("/sessions", response_model=list[ChatSession])
def list_sessions(
    user: CurrentUserDep, session: DbSessionDep, limit: Annotated[int, Query(ge=1, le=50)] = 20
) -> list[ChatSession]:
    """会話の一覧(新しい順)。"""
    return service.list_sessions(session, user.id, limit)


@router.get("/usage", response_model=ChatUsage)
def get_usage(
    user: CurrentUserDep, session: DbSessionDep, now: NowDep, settings: SettingsDep
) -> ChatUsage:
    """今日の利用回数とトークン使用量(12-4)。"""
    return service.get_usage(session, user.id, now, settings)
