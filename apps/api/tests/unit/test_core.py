"""UT:共通基盤(設定・ログ・ミドルウェア・例外・レート制限・カーソル)。"""

import json
import logging
from datetime import UTC, datetime

import fakeredis
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, ValidationError
from redis import RedisError

from app.core import rate_limit
from app.core.config import Settings
from app.core.error_handlers import register_error_handlers
from app.core.exceptions import AppError, NotFoundError, RateLimitError
from app.core.logging import JsonFormatter, mask_text, mask_value, request_id_var
from app.core.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.schemas import decode_cursor, encode_cursor

BASE_SETTINGS = {
    "supabase_url": "https://x.supabase.co",
    "supabase_secret_key": "k",
    "database_url": "postgresql://u:p@h/db",
    "gemini_api_key": "g",
}


# ---------------------------------------------------------------- 設定(0-2・0-3)


class TestSettings:
    def test_secret_is_hidden_in_repr(self) -> None:
        """秘密情報は repr・str に出ない(8-6)。"""
        settings = Settings(**BASE_SETTINGS, _env_file=None)  # type: ignore[arg-type]
        assert "postgresql://u:p" not in repr(settings)
        assert settings.sqlalchemy_database_url == "postgresql+psycopg://u:p@h/db"

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("http://a.com", ["http://a.com"]),
            (" http://a.com , http://b.com ,", ["http://a.com", "http://b.com"]),
            ("", []),
        ],
    )
    def test_cors_origins(self, raw: str, expected: list[str]) -> None:
        settings = Settings(**BASE_SETTINGS, cors_allow_origins=raw, _env_file=None)  # type: ignore[arg-type]
        assert settings.cors_origins == expected

    def test_production_rejects_localhost_cors(self) -> None:
        """本番で localhost の CORS は起動時に止める。"""
        with pytest.raises(ValidationError, match="localhost"):
            Settings(**BASE_SETTINGS, app_env="production", metrics_token="t", _env_file=None)  # type: ignore[arg-type]

    def test_production_requires_metrics_token(self) -> None:
        with pytest.raises(ValidationError, match="METRICS_TOKEN"):
            Settings(  # type: ignore[arg-type]
                **BASE_SETTINGS,
                app_env="production",
                cors_allow_origins="https://a.app",
                _env_file=None,
            )

    def test_production_disables_docs(self) -> None:
        settings = Settings(  # type: ignore[arg-type]
            **BASE_SETTINGS,
            app_env="production",
            cors_allow_origins="https://a.app",
            metrics_token="t",
            _env_file=None,
        )
        assert settings.docs_enabled is False
        assert settings.is_production is True

    def test_empty_optional_secret_is_none(self) -> None:
        """.env.example をそのままコピーした空欄は「未設定」。"""
        settings = Settings(**BASE_SETTINGS, sentry_dsn="", smtp_host="", _env_file=None)  # type: ignore[arg-type]
        assert settings.sentry_dsn is None and settings.smtp_host is None

    def test_missing_required_value_fails(self) -> None:
        """必須項目が空なら起動時にエラー。"""
        with pytest.raises(ValidationError, match="supabase_url"):
            Settings(**{**BASE_SETTINGS, "supabase_url": ""}, _env_file=None)  # type: ignore[arg-type]

    def test_stories_rate_limit_default(self) -> None:
        """ストーリーの上限は、指定しなければ 5(0-2)。"""
        settings = Settings(**BASE_SETTINGS, _env_file=None)  # type: ignore[arg-type]
        assert settings.rate_limit_stories_per_minute == 5

    def test_stories_rate_limit_rejects_zero(self) -> None:
        """ストーリーの上限に 0 を指定すると、起動時にエラー(0-2)。"""
        with pytest.raises(ValidationError, match="rate_limit_stories_per_minute"):
            Settings(**BASE_SETTINGS, rate_limit_stories_per_minute=0, _env_file=None)  # type: ignore[arg-type]


# ---------------------------------------------------------------- ログのマスク(15-5)


class TestLogging:
    @pytest.mark.parametrize(
        ("text", "hidden"),
        [
            ("Authorization: Bearer abc.def.ghi", "abc.def.ghi"),
            ("token=eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl", "eyJzdWIiOi"),
            ("key sb_secret_ABCdef123", "ABCdef123"),
            ("gemini AIzaSyA1234567890abcdefghijk", "1234567890"),
            ("mail me: hanako@example.com", "hanako@example.com"),
        ],
    )
    def test_mask_text(self, text: str, hidden: str) -> None:
        assert hidden not in mask_text(text)

    def test_mask_value_hides_sensitive_keys(self) -> None:
        masked = mask_value("data", {"password": "p", "nested": {"api_key": "k"}, "name": "ok"})
        assert masked == {"password": "***", "nested": {"api_key": "***"}, "name": "ok"}

    def test_json_formatter_includes_request_id_and_extras(self) -> None:
        token = request_id_var.set("req-1")
        try:
            record = logging.makeLogRecord(
                {"msg": "hello", "levelname": "INFO", "name": "t", "status": 200, "token": "secret"}
            )
            data = json.loads(JsonFormatter().format(record))
        finally:
            request_id_var.reset(token)
        assert data["request_id"] == "req-1"
        assert data["status"] == 200
        assert data["token"] == "***"


# ---------------------------------------------------------------- ミドルウェア・例外ハンドラー


class Body(BaseModel):
    password: str
    age: int


def make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(
        BodySizeLimitMiddleware,
        default_limit=100,
        limit_for=lambda p: 1000 if p == "/big" else None,
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=True)
    app.add_middleware(RequestContextMiddleware)
    register_error_handlers(app)

    @app.get("/ok")
    def ok() -> dict[str, str]:
        return {"request_id": request_id_var.get() or ""}

    @app.get("/boom")
    def boom() -> None:
        raise RuntimeError("内部の秘密の情報")

    @app.get("/not-found")
    def not_found() -> None:
        raise NotFoundError(details={"id": 1})

    @app.get("/limited")
    def limited() -> None:
        raise RateLimitError(retry_after=30)

    @app.post("/echo")
    def echo(body: Body) -> dict[str, int]:
        return {"age": body.age}

    @app.post("/big")
    def big(body: dict[str, str]) -> dict[str, int]:
        return {"n": len(body)}

    return app


@pytest.fixture
def client() -> TestClient:
    return TestClient(make_app(), raise_server_exceptions=False)


class TestMiddleware:
    def test_request_id_is_generated_and_returned(self, client: TestClient) -> None:
        response = client.get("/ok")
        assert response.headers["X-Request-ID"] == response.json()["request_id"]
        assert len(response.headers["X-Request-ID"]) == 32

    def test_valid_incoming_request_id_is_kept(self, client: TestClient) -> None:
        response = client.get("/ok", headers={"X-Request-ID": "abc-123"})
        assert response.headers["X-Request-ID"] == "abc-123"

    def test_invalid_incoming_request_id_is_replaced(self, client: TestClient) -> None:
        """ログを汚す値(改行など)は使わない。"""
        response = client.get("/ok", headers={"X-Request-ID": "bad id\twith tab"})
        assert response.headers["X-Request-ID"] != "bad id\twith tab"

    def test_security_headers(self, client: TestClient) -> None:
        headers = client.get("/ok").headers
        assert headers["X-Content-Type-Options"] == "nosniff"
        assert headers["X-Frame-Options"] == "DENY"
        assert headers["Referrer-Policy"] == "no-referrer"
        assert headers["Content-Security-Policy"].startswith("default-src 'none'")
        assert "max-age" in headers["Strict-Transport-Security"]

    def test_body_over_limit_is_rejected_by_content_length(self, client: TestClient) -> None:
        response = client.post(
            "/echo", content=b"x" * 101, headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 413
        assert response.json()["code"] == "payload_too_large"

    def test_body_over_limit_is_rejected_without_content_length(self, client: TestClient) -> None:
        """Content-Length を付けずに(chunked で)送っても止まる。"""

        def chunks():  # type: ignore[no-untyped-def]
            yield b'{"a": "'
            yield b"x" * 200
            yield b'"}'

        response = client.post(
            "/echo", content=chunks(), headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 413

    def test_path_specific_limit(self, client: TestClient) -> None:
        response = client.post("/big", json={"a": "x" * 500})
        assert response.status_code == 200

    def test_unexpected_error_hides_details(self, client: TestClient) -> None:
        """500 では内部の情報を出さず、問い合わせ用の request_id だけ返す(5-5)。"""
        response = client.get("/boom")
        assert response.status_code == 500
        body = response.json()
        assert body["code"] == "internal_error"
        assert "秘密" not in response.text
        assert body["details"]["request_id"] == response.headers["X-Request-ID"]


class TestErrorHandlers:
    def test_app_error_format(self, client: TestClient) -> None:
        response = client.get("/not-found")
        assert response.status_code == 404
        assert response.json() == {
            "code": "not_found",
            "message": "見つかりません",
            "details": {"id": 1},
        }

    def test_rate_limit_has_retry_after(self, client: TestClient) -> None:
        response = client.get("/limited")
        assert response.status_code == 429
        assert response.headers["Retry-After"] == "30"

    def test_validation_error_does_not_echo_input(self, client: TestClient) -> None:
        """422 に入力値(パスワードなど)を含めない(5-4)。"""
        response = client.post("/echo", json={"password": "hunter2", "age": "abc"})
        assert response.status_code == 422
        body = response.json()
        assert body["code"] == "validation_error"
        assert body["details"][0]["field"] == "body.age"
        assert "hunter2" not in response.text

    def test_unknown_route(self, client: TestClient) -> None:
        response = client.get("/nothing")
        assert response.status_code == 404
        assert response.json()["code"] == "http_404"

    def test_method_not_allowed(self, client: TestClient) -> None:
        response = client.delete("/ok")
        assert response.status_code == 405
        assert response.json()["message"] == "このメソッドは使えません"

    def test_app_error_default_message(self) -> None:
        assert str(AppError()) == "サーバーでエラーが発生しました"


# ---------------------------------------------------------------- レート制限(8-3・13-3)


class TestRateLimit:
    def test_allows_until_limit_then_blocks(self) -> None:
        redis = fakeredis.FakeRedis(decode_responses=True)
        results = [rate_limit.hit(redis, "posts:u1", limit=3, window_seconds=60) for _ in range(4)]
        assert [r.allowed for r in results] == [True, True, True, False]
        assert 0 < results[-1].retry_after <= 60

    def test_keys_are_per_user(self) -> None:
        redis = fakeredis.FakeRedis(decode_responses=True)
        assert rate_limit.hit(redis, "posts:u1", 1, 60).allowed
        assert rate_limit.hit(redis, "posts:u2", 1, 60).allowed

    def test_fail_open_when_redis_is_down(self) -> None:
        """Redis が落ちていても API は止めない。"""

        class BrokenRedis:
            def pipeline(self):  # type: ignore[no-untyped-def]
                raise RedisError("down")

        result = rate_limit.hit(BrokenRedis(), "k", 1, 60)  # type: ignore[arg-type]
        assert result.allowed is True


# ---------------------------------------------------------------- カーソル(4-2)


class TestCursor:
    def test_round_trip(self) -> None:
        created_at = datetime(2026, 10, 22, 1, 2, 3, tzinfo=UTC)
        assert decode_cursor(encode_cursor(created_at, 42)) == (created_at, 42)

    @pytest.mark.parametrize("cursor", ["", "!!!", "eyJ4IjoxfQ"])
    def test_broken_cursor_is_400(self, cursor: str) -> None:
        with pytest.raises(AppError) as exc:
            decode_cursor(cursor)
        assert exc.value.status_code == 400
