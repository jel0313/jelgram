"""Celery のタスク。中身は handlers.py の関数を呼ぶだけにする。"""

from datetime import UTC, datetime, timedelta
from functools import lru_cache

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.chat.ai_client import GeminiClient
from app.core.config import get_settings
from app.core.db import get_engine
from app.media.storage import SupabaseStorage
from app.stories.service import expire_stories as expire_stories_service
from app.worker import handlers
from app.worker.celery_app import celery_app
from app.worker.push import LogPushSender, WebPushSender


@lru_cache
def _clients() -> dict[str, object]:
    """ワーカーのプロセスごとに1回だけ作る(API の lifespan に当たる)。"""
    settings = get_settings()
    storage = SupabaseStorage(
        supabase_url=settings.supabase_url,
        secret_key=settings.supabase_secret_key.get_secret_value(),
        bucket=settings.media_bucket,
    )
    ai = GeminiClient(
        api_key=settings.gemini_api_key.get_secret_value(),
        model=settings.gemini_model,
        base_url=settings.gemini_base_url,
        timeout=settings.gemini_timeout_seconds,
        max_retries=settings.gemini_max_retries,
    )
    push = (
        WebPushSender(settings.vapid_private_key.get_secret_value(), settings.vapid_subject)
        if settings.vapid_private_key
        else LogPushSender()
    )
    return {"storage": storage, "ai": ai, "push": push, "settings": settings}


@celery_app.task
def relay_outbox() -> int:
    clients = _clients()
    with Session(get_engine()) as session:
        dispatch = handlers.make_dispatcher(
            session,
            storage=clients["storage"],  # type: ignore[arg-type]
            ai=clients["ai"],  # type: ignore[arg-type]
            push=clients["push"],  # type: ignore[arg-type]
            settings=clients["settings"],  # type: ignore[arg-type]
        )
        return handlers.relay_outbox(session, dispatch)


@celery_app.task
def expire_stories() -> int:
    """24時間を過ぎたストーリーを消す(11-5)。"""
    with Session(get_engine()) as session:
        return expire_stories_service(session, datetime.now(UTC))


@celery_app.task
def cleanup() -> None:
    """古いデータの掃除:冪等性キー(1日)・処理済み Outbox(7日)・Webhook の受信記録(30日)。"""
    now = datetime.now(UTC)
    with Session(get_engine()) as session:
        session.execute(
            text("delete from idempotency_keys where created_at < :t"),
            {"t": now - timedelta(days=1)},
        )
        session.execute(
            text("delete from outbox_events where processed_at < :t"),
            {"t": now - timedelta(days=7)},
        )
        session.execute(
            text("delete from webhook_events where received_at < :t"),
            {"t": now - timedelta(days=30)},
        )
        session.commit()
