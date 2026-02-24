import unittest
import os
import re

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
        self.assertEqual(settings.cors_allow_origins, ["https://a.example", "https://b.example"])
        self.assertEqual(settings.CORS_ALLOW_METHODS, ["GET", "POST"])
        self.assertEqual(settings.CORS_ALLOW_HEADERS, ["Authorization", "Content-Type"])

    def test_yandex_cors_regex_allows_website_and_storage_hosts(self) -> None:
        settings = Settings(
            **self._base_kwargs(),
            CORS_ALLOW_ORIGIN_REGEX=r"^https://[a-zA-Z0-9-]+\.(website|storage)\.yandexcloud\.net$",
        )

        pattern = re.compile(settings.CORS_ALLOW_ORIGIN_REGEX or "")
        self.assertTrue(pattern.match("https://hacknet-frontend.website.yandexcloud.net"))
        self.assertTrue(pattern.match("https://hacknet-frontend.storage.yandexcloud.net"))

    def test_default_cors_origins_include_hacknet_domains(self) -> None:
        default_origins = str(Settings.model_fields["CORS_ALLOW_ORIGINS"].default or "")
        self.assertIn("https://hacknet.tech", default_origins)
        self.assertIn("https://www.hacknet.tech", default_origins)


if __name__ == "__main__":
    unittest.main()
