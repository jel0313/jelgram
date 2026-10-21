"""ジョブキュー(Celery。11-4)。

API とは別のプロセスで、重い処理・時間のかかる処理・定期的な処理を動かす。

    API ──(DB の outbox_events)──→ ワーカー:relay_outbox(5秒ごと)
    beat(時計役)──→ ワーカー:expire_stories(1時間ごと)・cleanup(1日ごと)

起動(apps/api で):
    uv run celery -A app.worker.celery_app worker --loglevel=INFO
    uv run celery -A app.worker.celery_app beat --loglevel=INFO
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings
from app.core.logging import setup_logging

settings = get_settings()
setup_logging(settings.log_level, json_format=settings.log_json)

celery_app = Celery("jelgram", broker=settings.redis_url, include=["app.worker.tasks"])

celery_app.conf.update(
    timezone="UTC",
    # 処理が終わってから「受け取った」と返す。途中で落ちたら別のワーカーがやり直す
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,  # 重いジョブを1つのワーカーが抱え込まない
    task_time_limit=120,
    task_soft_time_limit=100,
    broker_connection_retry_on_startup=True,
    worker_hijack_root_logger=False,  # ログの形式は自分で決めたもの(JSON)を使う
    beat_schedule={
        "relay-outbox": {"task": "app.worker.tasks.relay_outbox", "schedule": 5.0},
        "expire-stories": {
            "task": "app.worker.tasks.expire_stories",
            "schedule": crontab(minute=5),
        },
        "cleanup": {"task": "app.worker.tasks.cleanup", "schedule": crontab(hour=18, minute=30)},
    },
)
