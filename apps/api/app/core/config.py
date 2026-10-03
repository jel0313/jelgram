"""アプリの設定(環境変数・.env から読み込む)。"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """環境変数と .env から読み込む設定値。

    必須項目が未設定・空文字の場合は、生成時(= 起動時)に ValidationError になる。
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    supabase_url: str = Field(min_length=1)
    supabase_secret_key: str = Field(min_length=1)
    database_url: str = Field(min_length=1)
    supabase_storage_bucket: str = "post-images"

    # Gemini API
    gemini_api_key: str = Field(min_length=1)
    gemini_model: str = "gemini-3.5-flash-lite"

    # レート制限(要件定義書 4.2)
    rate_limit_per_user_per_minute: int = Field(default=10, ge=1)
    rate_limit_per_user_per_day: int = Field(default=30, ge=1)
    rate_limit_global_per_minute: int = Field(default=12, ge=1)
    rate_limit_global_per_day: int = Field(default=400, ge=1)

    # CORS で許可するオリジン(カンマ区切り)
    cors_allow_origins: str = "http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        """cors_allow_origins をリストに変換する(前後の空白・空の要素は除く)。"""
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @property
    def sqlalchemy_database_url(self) -> str:
        """database_url を SQLAlchemy(psycopg 3)用の形に変換する。"""
        return self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)


@lru_cache
def get_settings() -> Settings:
    """設定を返す。初回に読み込んだものを使い回す。"""
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
