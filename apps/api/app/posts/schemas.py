"""投稿・いいねの入出力の形。"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, StringConstraints

from app.posts.constants import CONTENT_MAX_LENGTH


class AuthorResponse(BaseModel):
    id: UUID
    display_name: str
    avatar_url: str | None


class PostResponse(BaseModel):
    id: int
    content: str
    image_url: str | None
    created_at: datetime
    author: AuthorResponse
    like_count: int
    liked_by_me: bool


class PostCreate(BaseModel):
    content: Annotated[
        str,
        StringConstraints(strip_whitespace=True, min_length=1, max_length=CONTENT_MAX_LENGTH),
    ]
    image_url: str | None = None


class LikeResponse(BaseModel):
    post_id: int
    like_count: int
    liked_by_me: bool
