"""テスト共通の準備。

app.main は import された時点で設定を読むため、テスト用のダミー値を
import より前に環境変数へ設定する(環境変数は .env より優先されるため、本物のキーは使われない)。
"""

import os

os.environ["SUPABASE_URL"] = "https://test.supabase.co"
os.environ["SUPABASE_SECRET_KEY"] = "test-secret-key"
os.environ["DATABASE_URL"] = "postgresql://test:test@localhost:5432/test"
os.environ["GEMINI_API_KEY"] = "test-gemini-key"
os.environ["CORS_ALLOW_ORIGINS"] = "http://localhost:3000"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)
