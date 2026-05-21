from typing import Optional

import redis.asyncio as aioredis
from redis import Redis

from app.core.config import get_settings

settings = get_settings()

# Async Redis client for app use
_async_redis: Optional[aioredis.Redis] = None

# Sync Redis client for RQ workers
_sync_redis: Optional[Redis] = None


def get_async_redis() -> aioredis.Redis:
    global _async_redis
    if _async_redis is None:
        _async_redis = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            encoding="utf-8",
        )
    return _async_redis


def get_sync_redis() -> Redis:
    global _sync_redis
    if _sync_redis is None:
        _sync_redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _sync_redis


async def close_redis() -> None:
    global _async_redis
    if _async_redis:
        await _async_redis.aclose()
        _async_redis = None
