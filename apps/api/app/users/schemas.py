"""ユーザーの入出力の形。

他人に見せる形(UserProfile)と、自分にだけ見せる形(MeResponse)を分ける。
メールアドレス・ロールは MeResponse にしか入れない(1-5)。
"""

from datetime import datetime
from typing import Annotated, Any, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from app.posts.schemas import Author
from app.users.constants import RESERVED_USERNAMES, USERNAME_PATTERN

FollowStatus = Literal["none", "pending", "following"]


class UserProfile(Author):
    """他人から見たプロフィール。"""

    bio: str
    is_private: bool
    follower_count: int
    following_count: int
    post_count: int
    created_at: datetime
    follow_status: FollowStatus = Field(description="自分からこの人へのフォローの状態")
    follows_me: bool
    blocked_by_me: bool


class MeResponse(Author):
    """自分のアカウント情報(本人にだけ返す)。"""

    email: EmailStr | None
    bio: str
    is_private: bool
    role: Literal["user", "admin"]
    created_at: datetime


class ProfileUpdate(BaseModel):
    """プロフィールの変更(PATCH。送った項目だけ変わる)。"""

    model_config = ConfigDict(extra="forbid")

    username: Annotated[str, StringConstraints(pattern=USERNAME_PATTERN)] | None = Field(
        default=None, description="半角英小文字・数字・_ の 3〜30 文字", examples=["hanako_01"]
    )
    display_name: (
        Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)] | None
    ) = None
    bio: Annotated[str, StringConstraints(strip_whitespace=True, max_length=150)] | None = None
    is_private: bool | None = None

    @field_validator("username", mode="before")
    @classmethod
    def _lower(cls, value: Any) -> Any:
        """大文字で送られても小文字にそろえる(Hanako と hanako を別人にしない)。"""
        return value.lower() if isinstance(value, str) else value

    @field_validator("username")
    @classmethod
    def _not_reserved(cls, value: str | None) -> str | None:
        if value in RESERVED_USERNAMES:
            raise ValueError("このユーザー名は使えません")
        return value

    @model_validator(mode="after")
    def _check(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("変更する項目を1つ以上指定してください")
        for name in self.model_fields_set:
            if getattr(self, name) is None:
                raise ValueError(f"{name} に null は指定できません")
        return self


class UserSearchResult(Author):
    is_private: bool


class FollowResponse(BaseModel):
    follow_status: FollowStatus


class FollowRequest(BaseModel):
    """自分に届いたフォローリクエスト。"""

    user: Author
    created_at: datetime


class AccountExport(BaseModel):
    """個人データのエクスポート(21-3)。"""

    exported_at: datetime
    profile: dict[str, Any]
    posts: list[dict[str, Any]]
    comments: list[dict[str, Any]]
    likes: list[dict[str, Any]]
    following: list[dict[str, Any]]
    followers: list[dict[str, Any]]
    chat_messages: list[dict[str, Any]]


class UserId(BaseModel):
    id: UUID
