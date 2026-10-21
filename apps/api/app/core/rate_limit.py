"""Redis を使った固定ウィンドウ方式のレート制限(8-3・13-3)。

    キー rl:<名前>:<ユーザー>:<窓の番号> を INCR → 初回だけ有効期限を付ける
    回数が上限を超えたら拒否

Redis が落ちているときは「制限しない」で通す(fail-open)。
レート制限のために API 全体が止まるほうが困るため。止める必要がある AI チャットは DB で別に数える。
"""

import logging
import time
from dataclasses import dataclass

from redis import Redis, RedisError

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after: int  # 次の窓まで何秒か


def hit(redis: Redis, key: str, limit: int, window_seconds: int) -> RateLimitResult:
    """1回分を数えて、上限以内かを返す。"""
    now = int(time.time())
    window = now // window_seconds
    redis_key = f"rl:{key}:{window}"
    try:
        pipe = redis.pipeline()  # INCR と EXPIRE を1往復で送る
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds + 1, nx=True)
        count, _ = pipe.execute()
    except RedisError:
        logger.warning("Redis に接続できないため、レート制限をスキップしました", extra={"key": key})
        return RateLimitResult(allowed=True, retry_after=0)
    retry_after = window_seconds - (now % window_seconds)
    return RateLimitResult(allowed=int(count) <= limit, retry_after=retry_after)
