"""postsの入出力の形。"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class Author(BaseModel):
    """投稿の作成者。"""

    id: UUID
    display_name: str
    avatar_url: str | None


class PostResponse(BaseModel):
    """投稿の取得レスポンス。"""

    id: int
    content: str
    image_url: str | None
    created_at: datetime
    author: Author
    like_count: int
    liked_by_me: bool
