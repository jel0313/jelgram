"""アプリの設定(環境変数・.env から読み込む)。

読み込む順番(後ろほど優先):.env → .env.<APP_ENV> → 環境変数
例:APP_ENV=test のときは .env.test の値で .env を上書きできる。
"""

import os
from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

AppEnv = Literal["development", "test", "production"]


class Settings(BaseSettings):
    """環境変数と .env から読み込む設定値。

    必須項目が未設定・空文字の場合は、生成時(= 起動時)に ValidationError になる。
    秘密情報は SecretStr にして、ログや例外に値が出ないようにする(8-6)。
    """

    model_config = SettingsConfigDict(
        env_file=(".env", f".env.{os.getenv('APP_ENV', 'development')}"),
        extra="ignore",
    )

    # 実行環境(0-3)
    app_env: AppEnv = "development"
    log_level: str = "INFO"
    log_json: bool = True

    # Supabase
    supabase_url: str = Field(min_length=1)
    supabase_secret_key: SecretStr = Field(min_length=1)
    database_url: SecretStr = Field(min_length=1)
    supabase_storage_bucket: str = "post-images"  # 1次の公開バケット(互換のため残す)
    media_bucket: str = "media"
    media_signed_url_expires_seconds: int = Field(default=600, ge=60, le=3600)

    # DB コネクションプール(22-4)
    db_pool_size: int = Field(default=5, ge=1)
    db_max_overflow: int = Field(default=5, ge=0)
    db_pool_timeout_seconds: int = Field(default=10, ge=1)
    db_statement_timeout_ms: int = Field(default=5000, ge=100)

    # Redis(キャッシュ・レート制限・ジョブキュー・トークン失効)
    redis_url: str = "redis://localhost:6379/0"

    # Gemini API
    gemini_api_key: SecretStr = Field(min_length=1)
    gemini_model: str = "gemini-3.5-flash-lite"
    gemini_base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    gemini_timeout_seconds: float = Field(default=20, gt=0)
    gemini_max_retries: int = Field(default=2, ge=0, le=5)

    # AI チャットのレート制限(要件定義書 4.2。DB で集計する)
    rate_limit_per_user_per_minute: int = Field(default=10, ge=1)
    rate_limit_per_user_per_day: int = Field(default=30, ge=1)
    rate_limit_global_per_minute: int = Field(default=12, ge=1)
    rate_limit_global_per_day: int = Field(default=400, ge=1)

    # API のレート制限(Redis で集計する。1分あたりの回数。8-3)
    rate_limit_posts_per_minute: int = Field(default=10, ge=1)
    rate_limit_comments_per_minute: int = Field(default=20, ge=1)
    rate_limit_likes_per_minute: int = Field(default=60, ge=1)
    rate_limit_follows_per_minute: int = Field(default=30, ge=1)
    rate_limit_uploads_per_minute: int = Field(default=20, ge=1)
    rate_limit_reports_per_minute: int = Field(default=10, ge=1)

    # リクエストサイズの上限(8-7)
    max_request_body_bytes: int = Field(default=1_048_576, ge=1024)  # 1MB
    max_upload_body_bytes: int = Field(default=6_291_456, ge=1024)  # 6MB(画像 5MB + 余裕)

    # CORS で許可するオリジン(カンマ区切り)
    cors_allow_origins: str = "http://localhost:3000"

    # メール送信(未設定なら送らない。11-3)
    smtp_host: str | None = None
    smtp_port: int = 54325
    smtp_from: str = "jelgram <no-reply@jelgram.local>"

    # Webhook の署名検証用の共有鍵(11-6)
    webhook_secret: SecretStr | None = None

    # Web Push(未設定なら送らない。11-7)
    vapid_private_key: SecretStr | None = None
    vapid_subject: str = "mailto:admin@jelgram.local"

    # 監視(22章)
    sentry_dsn: SecretStr | None = None
    metrics_token: SecretStr | None = None

    @field_validator(
        "smtp_host",
        "webhook_secret",
        "vapid_private_key",
        "sentry_dsn",
        "metrics_token",
        mode="before",
    )
    @classmethod
    def _empty_to_none(cls, value: object) -> object:
        """.env に「SENTRY_DSN=」のように空で書かれていたら、未設定(None)として扱う。"""
        return None if value == "" else value

    @model_validator(mode="after")
    def _check_production(self) -> "Settings":
        """本番で危ない設定を起動時に止める(1-4・8-1)。"""
        if self.app_env == "production":
            if any("localhost" in o or "127.0.0.1" in o for o in self.cors_origins):
                raise ValueError("本番の CORS_ALLOW_ORIGINS に localhost は指定できません")
            if self.metrics_token is None:
                raise ValueError("本番では METRICS_TOKEN が必須です")
        return self

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def docs_enabled(self) -> bool:
        """/docs を公開するか。本番では API の一覧を外に見せない。"""
        return not self.is_production

    @property
    def cors_origins(self) -> list[str]:
        """cors_allow_origins をリストに変換する(前後の空白・空の要素は除く)。"""
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def sqlalchemy_database_url(self) -> str:
        """database_url を SQLAlchemy(psycopg 3)用の形に変換する。"""
        return self.database_url.get_secret_value().replace(
            "postgresql://", "postgresql+psycopg://", 1
        )


@lru_cache
def get_settings() -> Settings:
    """設定を返す。初回に読み込んだものを使い回す。"""
    return Settings()  # 値は環境変数から入る


SettingsDep = Annotated[Settings, Depends(get_settings)]
