"""投稿・いいねの ORM モデル(supabase/migrations の posts・likes と同じ形)。"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.users.models import Profile


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey(Profile.id))
    content: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Like(Base):
    __tablename__ = "likes"

    user_id: Mapped[UUID] = mapped_column(ForeignKey(Profile.id), primary_key=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(Post.id), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
