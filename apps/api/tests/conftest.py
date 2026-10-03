"""テスト共通の準備。

app.main は import された時点で設定を読むため、テスト用のダミー値を
import より前に環境変数へ設定する(環境変数は .env より優先されるため、本物のキーは使われない)。
"""

import os

os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SECRET_KEY"] = "test-secret-key"
# DATABASE_URL は設定しない(.env の開発用 DB を使い、テストごとにロールバックする)
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["CORS_ALLOW_ORIGINS"] = "http://localhost:3000"

from collections.abc import Callable, Iterator  # noqa: E402
from contextlib import contextmanager  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402
from typing import Any  # noqa: E402
from uuid import UUID, uuid4  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.db import get_db, get_engine  # noqa: E402
from app.main import app  # noqa: E402

TEST_ISSUER = "https://test.supabase.co/auth/v1"


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def private_key() -> ec.EllipticCurvePrivateKey:
    """テスト用の ES256 秘密鍵(Supabase の秘密鍵の代わり)。"""
    return ec.generate_private_key(ec.SECP256R1())


@pytest.fixture
def make_token(private_key: ec.EllipticCurvePrivateKey) -> Callable[..., str]:
    """Supabase と同じ形の JWT を作る関数を返す。

    クレームは引数で上書きでき、None を渡すとそのクレームを取り除く。
    """

    def _make_token(key: Any = None, algorithm: str = "ES256", **claims: Any) -> str:
        now = datetime.now(UTC)
        payload = {
            "sub": str(uuid4()),
            "email": "test@example.com",
            "aud": "authenticated",
            "iss": TEST_ISSUER,
            "iat": now,
            "exp": now + timedelta(hours=1),
            "role": "authenticated",
        }
        payload.update(claims)
        payload = {name: value for name, value in payload.items() if value is not None}
        return jwt.encode(
            payload,
            private_key if key is None else key,
            algorithm=algorithm,
            headers={"kid": "test-key"},
        )

    return _make_token


@contextmanager
def rollback_session() -> Iterator[Session]:
    """開発用 DB のトランザクションの中で動くセッション。抜けるときに全部ロールバックする。

    中で session.commit() を呼んでも、セーブポイントの確定にとどまる(外側は確定しない)。
    """
    connection = get_engine().connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def db_session() -> Iterator[Session]:
    """テストが終わったら全部ロールバックする DB セッション。"""
    with rollback_session() as session:
        yield session


@pytest.fixture
def db_client(db_session: Session) -> Iterator[TestClient]:
    """API が db_session を使うように差し替えた TestClient。"""
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


def insert_test_user(session: Session, display_name: str = "テストユーザー") -> UUID:
    """auth.users にテスト用ユーザーを入れる(トリガーで profiles も作られる)。"""
    user_id = uuid4()
    session.execute(
        text(
            "insert into auth.users (id, email, raw_user_meta_data) "
            "values (:id, :email, jsonb_build_object('full_name', cast(:name as text)))"
        ),
        {"id": user_id, "email": f"{user_id}@example.com", "name": display_name},
    )
    return user_id


@pytest.fixture
def create_user(db_session: Session) -> Callable[..., UUID]:
    """テスト用ユーザーを作る関数を返す(db_session と一緒にロールバックされる)。"""
    return lambda display_name="テストユーザー": insert_test_user(db_session, display_name)
