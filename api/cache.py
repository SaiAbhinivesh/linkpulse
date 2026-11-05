import logging

import redis

from api.config import settings

logger = logging.getLogger("linkpulse")

redis_client = redis.Redis.from_url(
    settings.redis_url,
    decode_responses=True,
    socket_timeout=0.5,
    socket_connect_timeout=0.5,
)


def link_key(code: str) -> str:
    return f"link:{code}"


def get_cached_url(code: str) -> str | None:
    try:
        return redis_client.get(link_key(code))
    except redis.RedisError:
        logger.warning("Redis unavailable, skipping cache read")
        return None


def cache_url(code: str, url: str) -> None:
    try:
        redis_client.set(link_key(code), url, ex=settings.cache_ttl_seconds)
    except redis.RedisError:
        logger.warning("Redis unavailable, skipping cache write")
