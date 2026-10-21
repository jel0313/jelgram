"""テスト共通の準備(14-1)。

app.main は import された時点で設定を読むため、テスト用の値を import より前に環境変数へ設定する。
環境変数は .env より優先されるので、本物のキー・クラウドの DB は使われない。

    UT(tests/unit)       … DB・Redis・AI・ストレージを使わない。全部偽物に差し替える
    IT(tests/integration)… ローカルの Supabase(DB)と Redis を使う。AI・ストレージだけ偽物
"""

import os

os.environ["APP_ENV"] = "test"
os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SECRET_KEY"] = "test-secret-key"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["CORS_ALLOW_ORIGINS"] = "http://localhost:3000"
os.environ["LOG_LEVEL"] = "WARNING"
os.environ["WEBHOOK_SECRET"] = "test-webhook-secret"
# IT はローカルの Supabase(supabase start)の DB を使う。クラウドの無料枠を消費しない
os.environ["DATABASE_URL"] = os.getenv(
    "TEST_DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)
os.environ["REDIS_URL"] = os.getenv("TEST_REDIS_URL", "redis://127.0.0.1:6379/15")

for key in ("SMTP_HOST", "SENTRY_DSN", "METRICS_TOKEN", "VAPID_PRIVATE_KEY"):
    os.environ.pop(key, None)  # .env に書いてあっても、テストでは使わない(未設定にする)

from collections.abc import Iterator  # noqa: E402

import fakeredis  # noqa: E402
import pytest  # noqa: E402
from fastapi import FastAPI  # noqa: E402

from app.main import app as fastapi_app  # noqa: E402
from tests.fakes import FakeAI, FakeStorage  # noqa: E402


@pytest.fixture
def app() -> Iterator[FastAPI]:
    """偽物のクライアントを入れたアプリ。テストが終わったら差し替えを元に戻す。"""
    fastapi_app.state.redis = fakeredis.FakeRedis(decode_responses=True)
    fastapi_app.state.storage = FakeStorage()
    fastapi_app.state.ai_client = FakeAI()
    yield fastapi_app
    fastapi_app.dependency_overrides.clear()


@pytest.fixture
def fake_storage(app: FastAPI) -> FakeStorage:
    storage: FakeStorage = app.state.storage
    return storage


@pytest.fixture
def fake_ai(app: FastAPI) -> FakeAI:
    ai: FakeAI = app.state.ai_client
    return ai
