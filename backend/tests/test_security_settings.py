import unittest
import os

os.environ.setdefault("DB_HOST", "localhost")
os.environ.setdefault("DB_PORT", "5432")
os.environ.setdefault("DB_NAME", "app")
os.environ.setdefault("DB_USER", "user")
os.environ.setdefault("DB_PASSWORD", "pass")
os.environ.setdefault("SECRET_KEY", "secret")

from app.config import Settings


class SecuritySettingsTests(unittest.TestCase):
    def _base_kwargs(self) -> dict:
        return {
            "DB_HOST": "localhost",
            "DB_PORT": 5432,
            "DB_NAME": "app",
            "DB_USER": "user",
            "DB_PASSWORD": "pass",
            "SECRET_KEY": "secret",
        }

    def test_sql_echo_is_disabled_by_default(self) -> None:
        settings = Settings(**self._base_kwargs())
        self.assertFalse(settings.SQL_ECHO)

    def test_cors_csv_parsing(self) -> None:
        settings = Settings(
            **self._base_kwargs(),
            CORS_ALLOW_ORIGINS="https://a.example, https://b.example",
            CORS_ALLOW_METHODS="GET,POST",
            CORS_ALLOW_HEADERS='["Authorization", "Content-Type"]',
        )
        self.assertEqual(settings.CORS_ALLOW_ORIGINS, ["https://a.example", "https://b.example"])
        self.assertEqual(settings.CORS_ALLOW_METHODS, ["GET", "POST"])
        self.assertEqual(settings.CORS_ALLOW_HEADERS, ["Authorization", "Content-Type"])


if __name__ == "__main__":
    unittest.main()
