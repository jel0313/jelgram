"""FastAPI アプリの組み立て。

    lifespan(起動・終了)→ ミドルウェア → 例外ハンドラー → ルーター(/api/v1)

リクエストが通る順番(外側から):
    RequestContext → SecurityHeaders → BodySizeLimit → CORS → ルーター
"""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import APIRouter, FastAPI, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.chat.ai_client import GeminiClient
from app.chat.router import router as chat_router
from app.comments.router import router as comments_router
from app.core.config import Settings, get_settings
from app.core.db import get_engine
from app.core.error_handlers import register_error_handlers
from app.core.exceptions import NotFoundError
from app.core.logging import mask_value, setup_logging
from app.core.middleware import (
    BodySizeLimitMiddleware,
    RequestContextMiddleware,
    SecurityHeadersMiddleware,
)
from app.core.redis import create_redis
from app.health.router import router as health_router
from app.media.router import router as media_router
from app.media.storage import SupabaseStorage
from app.notifications.router import router as notifications_router
from app.posts.router import router as posts_router
from app.stories.router import router as stories_router
from app.users.router import router as users_router
from app.webhooks.router import router as webhooks_router

logger = logging.getLogger(__name__)

API_PREFIX = "/api/v1"  # バージョニング(16-2)。互換性のない変更は /api/v2 として並べて出す

OPENAPI_TAGS = [
    {"name": "auth", "description": "ログアウト(トークンの失効)"},
    {"name": "users", "description": "自分・ほかのユーザー・フォロー・ブロック・退会"},
    {"name": "posts", "description": "投稿・タイムライン・検索・いいね・通報"},
    {"name": "comments", "description": "コメント"},
    {"name": "media", "description": "画像のアップロード・取得"},
    {"name": "stories", "description": "24時間で消える投稿"},
    {"name": "notifications", "description": "通知・プッシュ通知の登録"},
    {"name": "chat", "description": "AI チャット"},
    {"name": "admin", "description": "管理者専用"},
    {"name": "webhooks", "description": "外部サービスからの通知(署名で認証)"},
    {"name": "health", "description": "死活監視(認証不要)"},
]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """起動時に外部サービスのクライアントを作り、終了時に片付ける(17-5)。

    `@app.on_event("startup")` は非推奨。lifespan なら、作る処理と片付ける処理を1か所に書ける。
    """
    settings = get_settings()
    app.state.redis = create_redis(settings.redis_url)
    app.state.storage = SupabaseStorage(
        supabase_url=settings.supabase_url,
        secret_key=settings.supabase_secret_key.get_secret_value(),
        bucket=settings.media_bucket,
    )
    app.state.ai_client = GeminiClient(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        base_url=settings.gemini_base_url,
        timeout=settings.gemini_timeout_seconds,
        max_retries=settings.gemini_max_retries,
    )
    logger.info("起動しました", extra={"app_env": settings.app_env})
    yield
    # グレースフルシャットダウン(22-5)
    # Uvicorn が処理中のリクエストを終えるのを待ってから、ここに来る
    app.state.ai_client.close()
    app.state.storage.close()
    app.state.redis.close()
    get_engine().dispose()  # DB の接続を全部閉じる
    logger.info("終了しました")


def _init_sentry(settings: Settings) -> None:
    """エラー監視(22-2)。DSN が設定されているときだけ有効(無料プランの範囲で使う)。"""
    if settings.sentry_dsn is None:
        return

    def before_send(event, hint):  # type: ignore[no-untyped-def]
        # 送る前に、トークン・パスワードなどを伏せる(15-5)
        return mask_value("event", event)

    sentry_sdk.init(
        dsn=settings.sentry_dsn.get_secret_value(),
        environment=settings.app_env,
        send_default_pii=False,  # IP アドレス・Cookie などの個人情報を送らない
        traces_sample_rate=0.1,
        before_send=before_send,
    )


def _upload_limit(settings: Settings):  # type: ignore[no-untyped-def]
    """画像を送る URL だけ、本文の上限を大きくする。"""

    def limit_for(path: str) -> int | None:
        if path in (f"{API_PREFIX}/media", f"{API_PREFIX}/me/avatar"):
            return settings.max_upload_body_bytes
        return None

    return limit_for


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level, json_format=settings.log_json)
    _init_sentry(settings)

    app = FastAPI(
        title="jelgram API",
        version="1.0.0",
        description="AI が常駐するミニ SNS の API。認証は Supabase Auth の JWT(Bearer)。",
        openapi_tags=OPENAPI_TAGS,
        lifespan=lifespan,
        # 本番では API の一覧(/docs)を公開しない(0-3・8-8)
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url="/redoc" if settings.docs_enabled else None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
        # OpenTelemetry(22-3)。死活監視とメトリクスは記録しない
        telemetry={
            "exclude": lambda scope: scope["path"] in ("/health", "/health/live", "/metrics")
        },
    )

    # ミドルウェア:後から追加したものほど外側(先に通る)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,  # フロントのオリジンだけ(8-1)
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
        expose_headers=["X-Request-ID", "Retry-After"],
        allow_credentials=False,  # Cookie を使わない(トークンは Authorization ヘッダー。8-9)
        max_age=600,
    )
    app.add_middleware(
        BodySizeLimitMiddleware,
        default_limit=settings.max_request_body_bytes,
        limit_for=_upload_limit(settings),
    )
    app.add_middleware(SecurityHeadersMiddleware, hsts=settings.is_production)
    app.add_middleware(RequestContextMiddleware)

    register_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)
    for router in (
        auth_router,
        users_router,
        posts_router,
        comments_router,
        media_router,
        stories_router,
        notifications_router,
        chat_router,
        admin_router,
        webhooks_router,
    ):
        api.include_router(router)
    app.include_router(api)
    app.include_router(health_router)

    @app.get("/metrics", include_in_schema=False)
    def metrics(authorization: str | None = Header(default=None)) -> Response:
        """Prometheus 用のメトリクス(22-1)。

        本番ではトークンを知っている Prometheus だけが読める。
        """
        if settings.metrics_token is not None:
            expected = f"Bearer {settings.metrics_token.get_secret_value()}"
            if authorization != expected:
                raise NotFoundError
        return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
