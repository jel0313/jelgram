"""DB 接続(エンジン・セッション)。"""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.config import get_settings


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
