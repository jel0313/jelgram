"""投稿の入出力の形。

入力用(Create / Replace / Patch)と出力用(Response)を分ける(1-2)。
入力用には id・作成者・いいね数のような「クライアントに決めさせない項目」を入れない。
"""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.media.schemas import MediaOut
from app.posts.constants import CONTENT_MAX_LENGTH, MAX_MEDIA_PER_POST

# 前後の空白を除いてから、1〜500 文字かを確かめる(1-3)
Content = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=CONTENT_MAX_LENGTH)
]

# 並び順は、許可したものだけを受け付ける(4-4)。SQL に文字列を直接入れない
PostSort = Literal["new", "likes"]


class Author(BaseModel):
    """投稿・コメントの作成者。メールアドレスなどは含めない(1-5)。"""

    id: UUID
    username: str
    display_name: str
    avatar_url: str | None


class PostCreate(BaseModel):
    """投稿の作成。"""

    model_config = ConfigDict(extra="forbid")  # 想定外の項目(user_id など)が来たら 422

    content: Content = Field(examples=["今日のランチ #カレー"])
    media_ids: list[UUID] = Field(
        default_factory=list,
        max_length=MAX_MEDIA_PER_POST,
        description="先に POST /media で上げた画像の id。この順で並ぶ(最大 10 枚)",
    )

    @field_validator("media_ids")
    @classmethod
    def _no_duplicates(cls, value: list[UUID]) -> list[UUID]:
        if len(set(value)) != len(value):
            raise ValueError("同じ画像が2回指定されています")
        return value


class PostReplace(BaseModel):
    """投稿の編集(PUT:編集できる項目を全部送る。送らなかった項目もこの値で置き換わる)。"""

    model_config = ConfigDict(extra="forbid")

    content: Content
    comments_disabled: bool
    version: int = Field(ge=1, description="取得したときの version(楽観的ロック)")


class PostPatch(BaseModel):
    """投稿の編集(PATCH:変えたい項目だけ送る)。

    サービスでは `model_dump(exclude_unset=True)` で「送られてきた項目」だけを取り出す(3-4)。
    """

    model_config = ConfigDict(extra="forbid")

    content: Content | None = None
    comments_disabled: bool | None = None
    version: int = Field(ge=1, description="取得したときの version(楽観的ロック)")

    @model_validator(mode="after")
    def _check(self) -> Self:
        changed = self.model_fields_set - {"version"}
        if not changed:
            raise ValueError("変更する項目を1つ以上指定してください")
        for name in changed:
            if getattr(self, name) is None:
                raise ValueError(f"{name} に null は指定できません")
        return self


class PostResponse(BaseModel):
    """投稿(一覧・詳細で共通の形)。"""

    id: int
    content: str
    image_url: str | None = Field(description="1次の画像(互換のため)。新しい画像は media")
    media: list[MediaOut]
    hashtags: list[str]
    created_at: datetime
    updated_at: datetime
    author: Author
    like_count: int
    comment_count: int
    liked_by_me: bool
    comments_disabled: bool
    version: int


class LikeResponse(BaseModel):
    """いいね・取り消しの結果。"""

    post_id: int
    like_count: int
    liked_by_me: bool


class ReportCreate(BaseModel):
    """投稿の通報(7-5)。"""

    reason: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
