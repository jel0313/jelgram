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
from uuid import UUID, uuid4  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.core.db import engine, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def db_session() -> Iterator[Session]:
    """テストが終わったら全部ロールバックする DB セッション(開発用 DB を使う)。

    テストの中で session.commit() を呼んでも、セーブポイントの確定にとどまる(外側は確定しない)。
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection, join_transaction_mode="create_savepoint")

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def db_client(db_session: Session) -> Iterator[TestClient]:
    """API が db_session を使うように差し替えた TestClient。"""
    app.dependency_overrides[get_db] = lambda: db_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def create_user(db_session: Session) -> Callable[..., UUID]:
    """テスト用ユーザーを作る関数を返す(db_session と一緒にロールバックされる)。"""

    def _create_user(display_name: str = "テストユーザー") -> UUID:
        # auth.users に入れると、トリガーで profiles も作られる
        user_id = uuid4()
        db_session.execute(
            text(
                "insert into auth.users (id, email, raw_user_meta_data) "
                "values (:id, :email, jsonb_build_object('full_name', cast(:name as text)))"
            ),
            {"id": user_id, "email": f"{user_id}@example.com", "name": display_name},
        )
        return user_id

    return _create_user
