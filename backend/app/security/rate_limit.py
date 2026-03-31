from collections import defaultdict, deque
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Callable, DefaultDict

from fastapi import HTTPException, Request, status

from backend.app.config import settings


@dataclass(frozen=True)
class RateLimit:
    max_requests: int
    window_seconds: int


@dataclass(frozen=True)
class RateLimiter:
    key_func: Callable[[str], str]
    max_requests: int
    window_seconds: int


class InMemoryRateLimiter:
    """
    Simple in-memory limiter.
    Note: per-process only; use Redis or edge rate limiting for multi-instance production.
    """

    def __init__(self) -> None:
        self._events: DefaultDict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, rule: RateLimit) -> tuple[bool, int]:
        now = monotonic()
        cutoff = now - rule.window_seconds
        with self._lock:
            bucket = self._events[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= rule.max_requests:
                retry_after = max(1, int(rule.window_seconds - (now - bucket[0])))
                return False, retry_after

            bucket.append(now)
            return True, 0


rate_limiter = InMemoryRateLimiter()


def get_client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client:
        return request.client.host or "unknown"
    return "unknown"


def enforce_rate_limit(
    request: Request,
    *,
    scope: str,
    rule: RateLimit,
    subject: str = "anon",
) -> None:
    key = f"{scope}:{subject}:{get_client_ip(request)}"
    allowed, retry_after = rate_limiter.check(key, rule)
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Слишком много запросов. Повторите через {retry_after} сек.",
        )


# Password reset rate limiters
auth_forgot_password_email = RateLimiter(
    key_func=lambda email: f"auth:forgot_password:email:{email}",
    max_requests=settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_COUNT,
    window_seconds=settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW,
)

auth_reset_password_ip = RateLimiter(
    key_func=lambda ip: f"auth:reset_password:ip:{ip}",
    max_requests=settings.PASSWORD_RESET_CONFIRM_RATE_LIMIT_COUNT,
    window_seconds=settings.PASSWORD_RESET_CONFIRM_RATE_LIMIT_WINDOW,
)

