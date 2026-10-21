"""画像の入出力の形。"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.media.constants import MAX_IMAGE_BYTES

ContentType = Literal["image/jpeg", "image/png", "image/webp", "image/gif"]


class MediaOut(BaseModel):
    """投稿などに付く画像。URL は期限付き(既定 10 分)。"""

    id: UUID
    url: str | None = Field(description="署名付き URL。ストレージに接続できないときは null")
    thumbnail_url: str | None = None
    width: int | None = None
    height: int | None = None


class MediaResponse(MediaOut):
    """アップロードした画像。"""

    status: Literal["pending", "ready", "failed"]
    content_type: str
    size_bytes: int
    created_at: datetime


class MediaUrlResponse(BaseModel):
    """画像取得 API(9-6)の応答。"""

    url: str
    thumbnail_url: str | None
    expires_in: int


class UploadUrlRequest(BaseModel):
    """ブラウザから直接アップロードするための URL を作る(9-7)。"""

    content_type: ContentType
    size_bytes: int = Field(gt=0, le=MAX_IMAGE_BYTES)


class UploadUrlResponse(BaseModel):
    media_id: UUID
    upload_url: str = Field(description="この URL に PUT で画像を送る。送ったら complete を呼ぶ")
