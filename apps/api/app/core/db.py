"""DB 接続(エンジン・セッション)と、ORM モデルの親クラス。"""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session

from app.core.config import get_settings


class Base(DeclarativeBase):
    """すべての ORM モデルの親クラス。

    テーブルの作成・変更はマイグレーション(supabase/migrations)で行う。
    Base.metadata.create_all() は使わない。
    """


@lru_cache
def get_engine() -> Engine:
    """エンジン(コネクションプール)を返す。アプリ全体で1つを使い回す。"""
    settings = get_settings()
    return create_engine(settings.sqlalchemy_database_url, pool_pre_ping=True)


def get_db() -> Iterator[Session]:
    """リクエストごとに DB セッションを渡し、終わったら閉じる(接続をプールに返す)。"""
    with Session(get_engine()) as session:
        yield session


DbSessionDep = Annotated[Session, Depends(get_db)]
