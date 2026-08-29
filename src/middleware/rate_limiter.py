import time
from typing import Dict, Tuple
from fastapi import HTTPException, Request
from collections import defaultdict

from src.config import settings


class TokenBucket:
    def __init__(self, rate: int, burst: int):
        self.rate = rate
        self.burst = burst
        self.tokens = burst
        self.last_update = time.time()

    def consume(self, tokens: int = 1) -> bool:
        now = time.time()
        elapsed = now - self.last_update
        self.last_update = now

        self.tokens = min(self.burst, self.tokens + elapsed * (self.rate / 60.0))

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class RateLimiter:
    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = defaultdict(lambda: TokenBucket(
            rate=settings.rate_limiting.default_requests_per_minute,
            burst=settings.rate_limiting.burst_size
        ))

    def set_rate(self, key: str, rate: int, burst: int):
        self.buckets[key] = TokenBucket(rate=rate, burst=burst)

    def check_rate(self, key: str, rate: int, burst: int) -> Tuple[bool, int]:
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(rate=rate, burst=burst)

        bucket = self.buckets[key]
        bucket.rate = rate
        bucket.burst = burst

        allowed = bucket.consume()
        remaining = int(bucket.tokens)

        return allowed, remaining

    def clear_expired(self):
        now = time.time()
        expired_keys = [
            k for k, v in self.buckets.items()
            if now - v.last_update > 3600
        ]
        for k in expired_keys:
            del self.buckets[k]


rate_limiter = RateLimiter()


async def rate_limit_middleware(request: Request, call_next):
    if not settings.rate_limiting.enabled:
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    rate_limiter.clear_expired()

    allowed, remaining = rate_limiter.check_rate(
        client_ip,
        settings.rate_limiting.default_requests_per_minute,
        settings.rate_limiting.burst_size
    )

    if not allowed:
        raise HTTPException(
            status_code=429,
            detail={
                "message": "Rate limit exceeded",
                "type": "rate_limit_error",
                "code": 429
            }
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(remaining)
    return response


def check_api_key_rate_limit(api_key_id: str, rate_limit: int) -> Tuple[bool, int]:
    return rate_limiter.check_rate(
        api_key_id,
        rate_limit,
        max(1, rate_limit // 6)
    )
