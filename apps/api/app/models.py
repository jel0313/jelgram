"""ORM モデル(supabase/migrations のテーブル定義と同じ形)。

テーブルの作成・変更はマイグレーションで行う。Base.metadata.create_all() は使わない。
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, DateTime, ForeignKey, Identity, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    display_name: Mapped[str] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"))
    content: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Like(Base):
    __tablename__ = "likes"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("profiles.id"), primary_key=True)
    post_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("posts.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
