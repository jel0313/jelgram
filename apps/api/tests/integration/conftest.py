"""IT の準備(14-5・14-7)。

本物を使うもの:DB(ローカルの Supabase)・Redis・JWT の検証処理・全部の層
偽物にするもの:AI API・ストレージ・Supabase の公開鍵(テスト用の鍵で署名する)

DB はテストごとにロールバックする。テストの中の commit はセーブポイントの確定にとどまる。
事前に `supabase start` と `docker compose up -d redis` が必要。
"""

from collections.abc import AsyncIterator, Callable, Iterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import httpx2
import pytest
from fastapi import FastAPI
from redis import Redis, RedisError
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_jwks_client
from app.core.config import get_settings
from app.core.db import get_db, get_engine
from app.core.redis import create_redis
from tests.fakes import FakeJWKSClient, make_token


@pytest.fixture(scope="session", autouse=True)
def _require_services() -> None:
    """DB・Redis が起動していなければ、理由を出して IT を止める。"""
    try:
        with get_engine().connect() as connection:
            connection.execute(text("select 1 from public.posts limit 1"))
    except OperationalError:
        pytest.exit("IT にはローカルの DB が必要です:supabase start", returncode=2)
    try:
        create_redis(get_settings().redis_url).ping()
    except RedisError:
        pytest.exit("IT には Redis が必要です:docker compose up -d redis", returncode=2)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def db_session() -> Iterator[Session]:
    """テストが終わったら全部ロールバックする DB セッション。"""
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    # 開発で使った DB に残っている未処理のイベントを、このテストの間だけ処理済みにする
    # (ワーカーのテストが、テストの外で積まれたイベントまで処理しないように)
    session.execute(
        text("update outbox_events set processed_at = now() where processed_at is null")
    )
    yield session
    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def redis() -> Iterator[Redis]:
    """本物の Redis(テスト専用の DB 番号 15)。前後で空にする。"""
    client = create_redis(get_settings().redis_url)
    client.flushdb()
    yield client
    client.flushdb()
    client.close()


@pytest.fixture
def it_app(app: FastAPI, db_session: Session, redis: Redis) -> FastAPI:
    """DB・Redis は本物、JWKS だけ差し替えたアプリ。認証の処理(get_current_user)は本物を通す。"""
    app.state.redis = redis
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_jwks_client] = FakeJWKSClient
    return app


@pytest.fixture
async def client(it_app: FastAPI) -> AsyncIterator[httpx2.AsyncClient]:
    """API を呼ぶクライアント(httpx2.AsyncClient。サーバーを起動せずにアプリを直接呼ぶ)。"""
    transport = httpx2.ASGITransport(app=it_app)
    async with httpx2.AsyncClient(transport=transport, base_url="http://test/api/v1") as c:
        yield c


@dataclass
class User:
    id: UUID
    username: str
    headers: dict[str, str]


@pytest.fixture
def create_user(db_session: Session) -> Callable[..., User]:
    """テスト用ユーザーを作る関数を返す。auth.users に入れると、トリガーで profiles もできる。"""
    counter = iter(range(1, 10_000))

    def _create(
        name: str = "テストユーザー",
        *,
        private: bool = False,
        role: str = "user",
        username: str | None = None,
    ) -> User:
        user_id = uuid4()
        username = username or f"user{next(counter)}_{user_id.hex[:6]}"
        db_session.execute(
            text("""
                insert into auth.users (id, email, raw_user_meta_data)
                values (:id, :email, jsonb_build_object('full_name', cast(:name as text)))
            """),
            {"id": user_id, "email": f"{username}@example.com", "name": name},
        )
        db_session.execute(
            text("update profiles set username = :u, is_private = :p, role = :r where id = :id"),
            {"u": username, "p": private, "r": role, "id": user_id},
        )
        token = make_token(user_id, session_id=f"s-{user_id.hex[:8]}")
        return User(id=user_id, username=username, headers={"Authorization": f"Bearer {token}"})

    return _create
