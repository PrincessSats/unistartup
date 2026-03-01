import os
import unittest
from datetime import timedelta

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "app")
os.environ.setdefault("DB_USER", "user")
os.environ.setdefault("DB_PASSWORD", "pass")
os.environ.setdefault("SECRET_KEY", "secret")

from app.auth.security import (  # noqa: E402
    build_access_token,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)


class AuthSecurityTests(unittest.TestCase):
    def test_generate_refresh_token_is_non_empty_and_unique(self) -> None:
        token_a = generate_refresh_token()
        token_b = generate_refresh_token()
        self.assertTrue(token_a)
        self.assertTrue(token_b)
        self.assertNotEqual(token_a, token_b)

    def test_hash_refresh_token_is_stable(self) -> None:
        token = "sample-token"
        digest_a = hash_refresh_token(token)
        digest_b = hash_refresh_token(token)
        self.assertEqual(digest_a, digest_b)
        self.assertNotEqual(digest_a, token)
        self.assertEqual(len(digest_a), 64)

    def test_build_access_token_contains_sub_and_exp(self) -> None:
        token, expires_at = build_access_token(
            data={"sub": "user@example.com"},
            expires_delta=timedelta(minutes=5),
        )
        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("sub"), "user@example.com")
        self.assertIn("exp", payload)
        self.assertIsNotNone(expires_at)

    def test_create_access_token_compat_wrapper(self) -> None:
        token = create_access_token({"sub": "wrapper@example.com"})
        payload = decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload.get("sub"), "wrapper@example.com")


if __name__ == "__main__":
    unittest.main()
