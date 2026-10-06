"""DB 接続(エンジン・セッション)。"""

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.config import get_settings

# エンジン(コネクションプール)。アプリ全体で1つを使い回す
engine = create_engine(get_settings().sqlalchemy_database_url, pool_pre_ping=True)


def get_db() -> Iterator[Session]:
    """リクエストごとに DB セッションを渡し、終わったら閉じる(接続をプールに返す)。"""
    with Session(engine) as session:
        yield session


DbSessionDep = Annotated[Session, Depends(get_db)]
