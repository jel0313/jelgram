"""通知の入出力の形。"""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, StringConstraints

from app.posts.schemas import Author


class NotificationResponse(BaseModel):
    id: int
    type: Literal["like", "comment", "follow", "follow_request", "follow_accepted"]
    actor: Author
    post_id: int | None
    comment_id: int | None
    read: bool
    created_at: datetime


class UnreadCountResponse(BaseModel):
    unread: int


class MarkReadRequest(BaseModel):
    ids: list[int] | None = Field(default=None, max_length=100, description="省略すると全部既読")


Base64Key = Annotated[
    str, StringConstraints(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_\-=]+$")
]


class PushSubscriptionKeys(BaseModel):
    p256dh: Base64Key
    auth: Base64Key


class PushSubscriptionCreate(BaseModel):
    """ブラウザの PushManager.subscribe() の結果をそのまま送る形(11-7)。"""

    endpoint: HttpUrl
    keys: PushSubscriptionKeys


class PushSubscriptionDelete(BaseModel):
    endpoint: HttpUrl
