"""DB 接続(エンジン・セッション)。"""

from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    """エンジン(コネクションプール)を返す。アプリ全体で1つを使い回す。

    import した時点では接続しない。初めて使うときに作り、終了時に lifespan で dispose する。
    """
    settings = get_settings()
    engine = create_engine(
        settings.sqlalchemy_database_url,
        pool_pre_ping=True,  # 切れた接続を使う前に検知する
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_timeout=settings.db_pool_timeout_seconds,  # 空きを待つ秒数(22-4)
        pool_recycle=1800,  # 長く使った接続は作り直す(プーラー側の切断対策)
        connect_args={"connect_timeout": 5},
    )

    @event.listens_for(engine, "connect")
    def _set_statement_timeout(dbapi_connection: Any, _record: Any) -> None:
        # 遅い SQL がプールを占有し続けないよう、1文あたりの上限時間を決める(22-4)
        with dbapi_connection.cursor() as cursor:
            cursor.execute(f"set statement_timeout = {int(settings.db_statement_timeout_ms)}")
        dbapi_connection.commit()

    return engine


def get_db() -> Iterator[Session]:
    """リクエストごとに DB セッションを渡し、終わったら閉じる(接続をプールに返す)。"""
    with Session(get_engine()) as session:
        yield session


DbSessionDep = Annotated[Session, Depends(get_db)]
