"""認証の業務ロジック。"""

from datetime import UTC, datetime

from redis import Redis

from app.auth.constants import REVOKED_SESSION_KEY
from app.auth.schemas import CurrentUser


def logout(redis: Redis, user: CurrentUser, now: datetime | None = None) -> None:
    """セッションを、トークンの期限まで失効リストに入れる。"""
    if user.session_id is None or user.expires_at is None:
        return
    now = now or datetime.now(UTC)
    ttl = int((user.expires_at - now).total_seconds())
    if ttl > 0:
        redis.set(REVOKED_SESSION_KEY.format(session_id=user.session_id), "1", ex=ttl)
