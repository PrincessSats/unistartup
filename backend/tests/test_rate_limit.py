import unittest
from typing import List, Optional, Tuple

from fastapi import HTTPException
from starlette.requests import Request

from app.security.rate_limit import InMemoryRateLimiter, RateLimit, enforce_rate_limit


def _build_request(headers: Optional[List[Tuple[bytes, bytes]]] = None) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers or [],
        "client": ("127.0.0.1", 12345),
    }
    return Request(scope)


class RateLimitTests(unittest.TestCase):
    def test_limiter_blocks_after_threshold(self) -> None:
        limiter = InMemoryRateLimiter()
        rule = RateLimit(max_requests=2, window_seconds=60)

        allowed_1, _ = limiter.check("k", rule)
        allowed_2, _ = limiter.check("k", rule)
        allowed_3, retry_after = limiter.check("k", rule)

        self.assertTrue(allowed_1)
        self.assertTrue(allowed_2)
        self.assertFalse(allowed_3)
        self.assertGreaterEqual(retry_after, 1)

    def test_enforce_rate_limit_raises_429(self) -> None:
        request = _build_request()
        rule = RateLimit(max_requests=1, window_seconds=60)

        enforce_rate_limit(request, scope="unit", rule=rule, subject="user")
        with self.assertRaises(HTTPException) as ctx:
            enforce_rate_limit(request, scope="unit", rule=rule, subject="user")

        self.assertEqual(ctx.exception.status_code, 429)

    def test_forwarded_ip_changes_bucket(self) -> None:
        rule = RateLimit(max_requests=1, window_seconds=60)
        req_a = _build_request(headers=[(b"x-forwarded-for", b"10.0.0.1")])
        req_b = _build_request(headers=[(b"x-forwarded-for", b"10.0.0.2")])

        enforce_rate_limit(req_a, scope="ip-split", rule=rule, subject="same")
        # Different source IP should not share the same bucket.
        enforce_rate_limit(req_b, scope="ip-split", rule=rule, subject="same")


if __name__ == "__main__":
    unittest.main()
