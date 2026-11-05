import logging
import time

import redis
from fastapi import HTTPException, Request

from api.cache import redis_client
from api.config import settings

logger = logging.getLogger("linkpulse")

WINDOW_SECONDS = 60


def rate_limit_create(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    window = int(time.time() // WINDOW_SECONDS)
    key = f"rate:create:{ip}:{window}"

    try:
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, WINDOW_SECONDS)
        count, _ = pipe.execute()
    except redis.RedisError:
        logger.warning("Redis unavailable, skipping rate limit")
        return

    if count > settings.create_rate_limit_per_minute:
        retry_after = WINDOW_SECONDS - int(time.time()) % WINDOW_SECONDS
        raise HTTPException(
            status_code=429,
            detail="Too many links created. Try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )
