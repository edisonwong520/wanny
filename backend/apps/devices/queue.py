from __future__ import annotations

import os
from functools import lru_cache

from redis import Redis
from redis.exceptions import RedisError


DEFAULT_QUEUE_BACKEND = "polling"
REDIS_QUEUE_BACKEND = "redis"


def get_queue_backend() -> str:
    return str(os.getenv("DEVICE_SYNC_QUEUE_BACKEND", DEFAULT_QUEUE_BACKEND)).strip().lower() or DEFAULT_QUEUE_BACKEND


def redis_queue_enabled() -> bool:
    return get_queue_backend() == REDIS_QUEUE_BACKEND


def get_queue_name() -> str:
    return str(os.getenv("DEVICE_SYNC_QUEUE_NAME", "device_sync")).strip() or "device_sync"


def get_block_timeout() -> int:
    value = str(os.getenv("DEVICE_SYNC_QUEUE_BLOCK_TIMEOUT", "5")).strip()
    try:
        return max(1, int(value))
    except ValueError:
        return 5


@lru_cache(maxsize=1)
def get_redis_client() -> Redis:
    redis_url = str(os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")).strip()
    return Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=1,
        # Let BRPOP own the blocking behavior; a shorter socket timeout would turn
        # an idle queue wait into a false-positive Redis error.
        socket_timeout=None,
    )


def enqueue_account_refresh(account_id: int) -> bool:
    if not redis_queue_enabled():
        return False
    get_redis_client().lpush(get_queue_name(), str(account_id))
    return True


def dequeue_account_refresh(timeout: int | None = None) -> int | None:
    if not redis_queue_enabled():
        return None
    result = get_redis_client().brpop(get_queue_name(), timeout=timeout or get_block_timeout())
    if not result:
        return None
    _, payload = result
    return int(payload)


__all__ = [
    "RedisError",
    "dequeue_account_refresh",
    "enqueue_account_refresh",
    "get_block_timeout",
    "get_queue_backend",
    "get_queue_name",
    "get_redis_client",
    "redis_queue_enabled",
]
