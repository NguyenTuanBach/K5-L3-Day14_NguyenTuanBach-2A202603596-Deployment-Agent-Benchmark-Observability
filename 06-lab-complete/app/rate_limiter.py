"""Sliding-window rate limit bằng Redis sorted set (mỗi API key)."""
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW = 60


def check_rate_limit(key: str) -> None:
    rkey = f"rl:{key}"
    now = time.time()
    try:
        pipe = r.pipeline()
        pipe.zremrangebyscore(rkey, 0, now - WINDOW)
        pipe.zcard(rkey)
        _, count = pipe.execute()
        if count >= settings.rate_limit_per_minute:
            oldest = r.zrange(rkey, 0, 0, withscores=True)
            retry = max(1, int(WINDOW - (now - oldest[0][1])) + 1) if oldest else WINDOW
            raise HTTPException(status_code=429, detail="Rate limit exceeded",
                                headers={"Retry-After": str(retry)})
        pipe = r.pipeline()
        pipe.zadd(rkey, {f"{now}:{uuid.uuid4().hex[:8]}": now})
        pipe.expire(rkey, WINDOW + 5)
        pipe.execute()
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=503, detail="Rate limiter unavailable (Redis)")
