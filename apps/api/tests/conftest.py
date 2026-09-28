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

from collections.abc import Callable  # noqa: E402
from datetime import UTC, datetime, timedelta  # noqa: E402
from typing import Any  # noqa: E402
from uuid import uuid4  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from cryptography.hazmat.primitives.asymmetric import ec  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

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
