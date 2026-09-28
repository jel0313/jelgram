"""設定クラスのテスト(詳細設計書 7.2 T-04〜T-07)。

_env_file=None を渡して、ローカルの .env を読まずに Settings を生成する。
"""

import pytest
from pydantic import ValidationError

from app.core.config import Settings

REQUIRED = {
    "supabase_url": "https://test.supabase.co",
    "supabase_secret_key": "test-secret-key",
    "database_url": "postgresql://test:test@localhost:5432/test",
    "gemini_api_key": "test-gemini-key",
}


def test_cors_origins_splits_comma_separated_string() -> None:
    """T-04: カンマ区切りを分割し、前後の空白と空の要素を除く。"""
    settings = Settings(
        _env_file=None, **REQUIRED, cors_allow_origins="http://a.com, http://b.com,"
    )

    assert settings.cors_origins == ["http://a.com", "http://b.com"]


def test_empty_required_value_raises_error() -> None:
    """T-05: 必須項目が空文字だとエラーになる。"""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **{**REQUIRED, "gemini_api_key": ""})


def test_defaults_are_applied() -> None:
    """T-06: 省略した項目に初期値が入る。"""
    settings = Settings(_env_file=None, **REQUIRED)

    assert settings.gemini_model == "gemini-3.5-flash-lite"
    assert settings.rate_limit_global_per_day == 400


def test_rate_limit_must_be_positive() -> None:
    """T-07: レート制限に 0 以下を指定するとエラーになる。"""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **REQUIRED, rate_limit_per_user_per_minute=0)
