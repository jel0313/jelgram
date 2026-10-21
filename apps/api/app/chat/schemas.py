"""AI チャットの入出力の形。"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.chat.constants import MESSAGE_MAX_LENGTH, SESSION_ID_PATTERN

SessionId = Annotated[str, StringConstraints(pattern=SESSION_ID_PATTERN)]


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MESSAGE_MAX_LENGTH)
    ]
    session_id: SessionId = Field(description="会話のまとまり。「新しい会話」で新しい値にする")
    post_id: int | None = Field(default=None, description="「この投稿について」のときの投稿 id")


class ChatMessage(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    post_id: int | None
    created_at: datetime


class ChatResponse(BaseModel):
    session_id: str
    reply: ChatMessage


class ChatSession(BaseModel):
    session_id: str
    first_message: str
    last_message_at: datetime
    message_count: int


class ChatUsage(BaseModel):
    """今日の利用状況(12-4)。"""

    used_today: int
    limit_per_day: int
    prompt_tokens_today: int
    completion_tokens_today: int


class StreamDelta(BaseModel):
    text: str


class StreamDone(BaseModel):
    reply: ChatMessage


class StreamError(BaseModel):
    code: str
    message: str
