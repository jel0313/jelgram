"""認証(JWT 検証)のテスト(詳細設計書 8.2 T-01〜T-12)。

get_jwks_client を偽物に差し替え、本物の Supabase にはアクセスしない。
"""

from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient

from app.auth.dependencies import get_jwks_client
from app.main import app

TEST_ISSUER = "https://test.supabase.co/auth/v1"

client = TestClient(app)

# テスト用の ES256 秘密鍵(Supabase の秘密鍵の代わり)
private_key = ec.generate_private_key(ec.SECP256R1())


def make_token(key: Any = None, algorithm: str = "ES256", **claims: Any) -> str:
    """Supabase と同じ形の JWT を作る。

    クレームは引数で上書きでき、None を渡すとそのクレームを取り除く。
    """
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


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def fake_jwks_client() -> Iterator[None]:
    """どのトークンに対してもテスト用の公開鍵を返す、偽物の JWKS クライアントに差し替える。"""
    fake = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=private_key.public_key())
    )
    app.dependency_overrides[get_jwks_client] = lambda: fake
    yield
    app.dependency_overrides.clear()


def test_valid_token_returns_user() -> None:
    """T-01: 有効なトークンでユーザー情報が返る。"""
    user_id = "9f1c2b7e-3a4d-4e5f-8a6b-7c8d9e0f1a2b"

    response = client.get("/me", headers=_bearer(make_token(sub=user_id)))

    assert response.status_code == 200
    assert response.json() == {"id": user_id, "email": "test@example.com"}


def test_missing_header_is_rejected() -> None:
    """T-02: ヘッダーがないと拒否する。"""
    response = client.get("/me")

    assert response.status_code == 401
    assert response.json() == {"detail": "認証が必要です"}
    assert response.headers["www-authenticate"] == "Bearer"


def test_non_bearer_scheme_is_rejected() -> None:
    """T-03: Bearer 以外の方式は拒否する。"""
    response = client.get("/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})

    assert response.status_code == 401
    assert response.json() == {"detail": "認証が必要です"}


def test_malformed_token_is_rejected() -> None:
    """T-04: 形式が壊れたトークンを拒否する。"""
    response = client.get("/me", headers=_bearer("not-a-jwt"))

    assert response.status_code == 401
    assert response.json() == {"detail": "トークンが無効です"}
    assert response.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize(
    "claims",
    [
        pytest.param({"exp": datetime.now(UTC) - timedelta(minutes=1)}, id="T-05 expired"),
        pytest.param({"aud": "anon"}, id="T-07 wrong-aud"),
        pytest.param({"iss": "https://other.supabase.co/auth/v1"}, id="T-08 wrong-iss"),
        pytest.param({"exp": None}, id="T-10 no-exp"),
        pytest.param({"sub": "not-a-uuid"}, id="T-11 sub-not-uuid"),
    ],
)
def test_invalid_claims_are_rejected(claims: dict) -> None:
    """T-05・T-07・T-08・T-10・T-11: クレームが1つだけおかしいトークンを拒否する。"""
    response = client.get("/me", headers=_bearer(make_token(**claims)))

    assert response.status_code == 401
    assert response.json() == {"detail": "トークンが無効です"}


def test_token_signed_with_other_key_is_rejected() -> None:
    """T-06: 別の鍵で署名されたトークンを拒否する。"""
    other_key = ec.generate_private_key(ec.SECP256R1())

    response = client.get("/me", headers=_bearer(make_token(key=other_key)))

    assert response.status_code == 401


def test_disallowed_algorithm_is_rejected() -> None:
    """T-09: 許可していない署名方式(HS256)を拒否する。"""
    token = make_token(key="x" * 32, algorithm="HS256")

    response = client.get("/me", headers=_bearer(token))

    assert response.status_code == 401


def test_jwks_unreachable_returns_503() -> None:
    """T-12: Supabase につながらないときは 503 を返す。"""

    def raise_connection_error(token: str) -> None:
        raise jwt.PyJWKClientConnectionError("connection failed")

    app.dependency_overrides[get_jwks_client] = lambda: SimpleNamespace(
        get_signing_key_from_jwt=raise_connection_error
    )

    response = client.get("/me", headers=_bearer(make_token()))

    assert response.status_code == 503
    assert response.json() == {"detail": "認証サーバーに接続できません"}
