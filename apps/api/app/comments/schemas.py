"""コメントの入出力の形。"""

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

from app.posts.schemas import Author

CommentContent = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)
]


class CommentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: CommentContent


class CommentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: CommentContent


class CommentResponse(BaseModel):
    id: int
    post_id: int
    content: str
    author: Author
    created_at: datetime
    updated_at: datetime
    can_delete: bool  # 自分のコメント、または自分の投稿についたコメント(7-2)
