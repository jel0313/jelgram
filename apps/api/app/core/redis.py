"""Redis 接続(キャッシュ・レート制限・トークン失効で使う)。"""

from typing import Annotated

from fastapi import Depends, Request
from redis import Redis


def create_redis(url: str) -> Redis:
    """Redis クライアントを作る。中にコネクションプールを持つので、アプリ全体で1つを使い回す。

    タイムアウトを短くして、Redis が落ちても API 全体が待たされないようにする。
    """
    return Redis.from_url(
        url,
        decode_responses=True,
        socket_timeout=0.5,
        socket_connect_timeout=0.5,
        health_check_interval=30,
    )


def get_redis(request: Request) -> Redis:
    """lifespan で作った Redis クライアントを返す。"""
    redis: Redis = request.app.state.redis
    return redis


RedisDep = Annotated[Redis, Depends(get_redis)]
