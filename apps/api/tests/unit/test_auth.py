"""UT:認証・認可の依存関数(6-3・6-5・7-5)。DB は repository の差し替えで代用する。"""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import fakeredis
import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.auth import repository, service
from app.auth.dependencies import (
    AdminUserDep,
    CurrentUserDep,
    get_current_user,
    get_jwks_client,
    rate_limit,
)
from app.auth.schemas import CurrentUser
from app.core.db import get_db
from app.core.error_handlers import register_error_handlers
from app.core.redis import get_redis
from tests.fakes import FakeJWKSClient, make_token

USER_ID = uuid4()


@pytest.fixture
def account(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    """DB の代わり:repository.get_account が返すアカウントを差し替える。"""
    acc = SimpleNamespace(role="user", status="active", exists=True)
    monkeypatch.setattr(
        repository, "get_account", lambda session, user_id: acc if acc.exists else None
    )
    return acc


@pytest.fixture
def redis() -> fakeredis.FakeRedis:
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def client(account: SimpleNamespace, redis: fakeredis.FakeRedis) -> TestClient:
    app = FastAPI()
    register_error_handlers(app)
    app.dependency_overrides[get_jwks_client] = FakeJWKSClient
    app.dependency_overrides[get_db] = lambda: None
    app.dependency_overrides[get_redis] = lambda: redis

    @app.get("/me")
    def me(user: CurrentUserDep) -> dict[str, str]:
        return {"id": str(user.id), "role": user.role}

    @app.get("/admin")
    def admin(user: AdminUserDep) -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/limited", dependencies=[Depends(rate_limit("t", "rate_limit_posts_per_minute"))])
    def limited() -> dict[str, str]:
        return {"ok": "yes"}

    return TestClient(app)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


class TestGetCurrentUser:
    def test_valid_token(self, client: TestClient) -> None:
        response = client.get("/me", headers=auth(make_token(USER_ID)))
        assert response.status_code == 200
        assert response.json() == {"id": str(USER_ID), "role": "user"}

    def test_no_token_is_401(self, client: TestClient) -> None:
        response = client.get("/me")
        assert response.status_code == 401
        assert response.headers["WWW-Authenticate"] == "Bearer"
        assert response.json()["code"] == "unauthorized"

    @pytest.mark.parametrize(
        "token",
        [
            make_token(USER_ID, expires_in=-10),  # 期限切れ
            make_token(USER_ID, aud="anon"),  # audience 違い
            make_token(USER_ID, iss="https://evil.example.com/auth/v1"),  # 発行元違い
            make_token("not-a-uuid"),  # sub が UUID でない
            "not.a.jwt",
        ],
    )
    def test_invalid_tokens_are_401(self, client: TestClient, token: str) -> None:
        response = client.get("/me", headers=auth(token))
        assert response.status_code == 401
        assert response.json()["code"] == "invalid_token"

    def test_hs256_token_is_rejected(self, client: TestClient) -> None:
        """alg をすり替えたトークン(共通鍵で署名)は通さない。"""
        token = jwt.encode(
            {"sub": str(USER_ID)}, "s" * 32, algorithm="HS256", headers={"kid": "test-key"}
        )
        assert client.get("/me", headers=auth(token)).status_code == 401

    def test_revoked_session_is_401(self, client: TestClient, redis: fakeredis.FakeRedis) -> None:
        """ログアウト済みのセッションのトークンは使えない(6-5)。"""
        redis.set("revoked_session:s-1", "1")
        response = client.get("/me", headers=auth(make_token(USER_ID, session_id="s-1")))
        assert response.status_code == 401

    def test_suspended_user_is_403(self, client: TestClient, account: SimpleNamespace) -> None:
        account.status = "suspended"
        response = client.get("/me", headers=auth(make_token(USER_ID)))
        assert response.status_code == 403
        assert response.json()["code"] == "account_suspended"

    @pytest.mark.parametrize("state", ["deleted", "missing"])
    def test_deleted_or_missing_user_is_401(
        self, client: TestClient, account: SimpleNamespace, state: str
    ) -> None:
        if state == "deleted":
            account.status = "deleted"
        else:
            account.exists = False
        assert client.get("/me", headers=auth(make_token(USER_ID))).status_code == 401

    def test_jwks_connection_error_is_503(self, client: TestClient) -> None:
        class DownJWKS:
            def get_signing_key_from_jwt(self, token: str) -> None:
                raise jwt.PyJWKClientConnectionError("down")

        client.app.dependency_overrides[get_jwks_client] = DownJWKS  # type: ignore[attr-defined]
        assert client.get("/me", headers=auth(make_token(USER_ID))).status_code == 503


class TestRequireRole:
    def test_user_cannot_access_admin(self, client: TestClient) -> None:
        response = client.get("/admin", headers=auth(make_token(USER_ID)))
        assert response.status_code == 403

    def test_admin_can_access(self, client: TestClient, account: SimpleNamespace) -> None:
        account.role = "admin"
        assert client.get("/admin", headers=auth(make_token(USER_ID))).status_code == 200


class TestRateLimitDependency:
    def test_blocks_after_limit(self, client: TestClient) -> None:
        from app.core.config import get_settings

        limit = get_settings().rate_limit_posts_per_minute
        headers = auth(make_token(USER_ID))
        codes = [client.get("/limited", headers=headers).status_code for _ in range(limit + 1)]
        assert codes[:-1] == [200] * limit
        assert codes[-1] == 429


class TestLogout:
    def test_revokes_until_expiry(self) -> None:
        redis = fakeredis.FakeRedis(decode_responses=True)
        now = datetime(2026, 1, 1, tzinfo=UTC)
        user = CurrentUser(id=USER_ID, session_id="s-9", expires_at=now + timedelta(minutes=10))
        service.logout(redis, user, now)
        assert redis.get("revoked_session:s-9") == "1"
        assert 590 <= redis.ttl("revoked_session:s-9") <= 600

    def test_expired_token_needs_no_revocation(self) -> None:
        redis = fakeredis.FakeRedis(decode_responses=True)
        now = datetime(2026, 1, 1, tzinfo=UTC)
        user = CurrentUser(id=USER_ID, session_id="s-9", expires_at=now - timedelta(seconds=1))
        service.logout(redis, user, now)
        assert redis.get("revoked_session:s-9") is None

    def test_without_session_id_does_nothing(self) -> None:
        redis = fakeredis.FakeRedis(decode_responses=True)
        service.logout(redis, CurrentUser(id=USER_ID))
        assert redis.keys() == []


def test_get_current_user_override_is_possible() -> None:
    """UT では get_current_user を差し替えて、認証を飛ばせる(14-7)。"""
    app = FastAPI()

    @app.get("/me")
    def me(user: CurrentUserDep) -> dict[str, str]:
        return {"id": str(user.id)}

    app.dependency_overrides[get_current_user] = lambda: CurrentUser(id=USER_ID)
    assert TestClient(app).get("/me").json() == {"id": str(USER_ID)}
