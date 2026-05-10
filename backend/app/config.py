import json
from pathlib import Path
from typing import Any, Optional

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings

ENV_FILE_PATH = Path(__file__).resolve().parents[1] / ".env"
ROOT_ENV_FILE_PATH = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseSettings):
    """
    Настройки приложения.
    Автоматически читает переменные из .env файла
    """
    
    # База данных
    DB_HOST: str
    DB_PORT: int = 6432
    DB_NAME: str
    DB_USER: str
    DB_PASSWORD: str
    
    # JWT токены
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    # Short-lived access token; session continuity comes from rotating refresh tokens.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_HOURS: int = 48
    REFRESH_TOKEN_COOKIE_NAME: str = "refresh_token"
    REFRESH_TOKEN_COOKIE_PATH: str = "/"
    REFRESH_TOKEN_COOKIE_DOMAIN: str = ""
    REFRESH_TOKEN_COOKIE_SECURE: bool = False
    REFRESH_TOKEN_COOKIE_SAMESITE: str = "lax"
    SQL_ECHO: bool = False
    # In serverless/autoscale this should stay disabled to avoid cold-start penalties.
    RUN_STARTUP_DB_MAINTENANCE: bool = False
    LOG_SLOW_REQUESTS: bool = True
    SLOW_REQUEST_THRESHOLD_MS: int = 1000

    # CORS
    CORS_ALLOW_ORIGINS: str = (
        # Локальные origin'ы для CRA/Vite/preview, чтобы dev-запуск не ломался на CORS.
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:4173,"
        "http://127.0.0.1:4173,"
        "https://hacknet.tech,"
        "https://www.hacknet.tech,"
        "https://storage.yandexcloud.net"
    )
    CORS_ALLOW_ORIGIN_REGEX: Optional[str] = (
        r"^https://[a-zA-Z0-9-]+\.(website|storage)\.yandexcloud\.net$"
    )
    # Required for refresh-token HttpOnly cookie flow.
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list[str] = ["Authorization", "Content-Type", "X-Auth-Token"]
    
    # Yandex Object Storage (S3-совместимое хранилище)
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET_NAME: str = ""
    S3_TASK_BUCKET_NAME: str = ""
    S3_ENDPOINT_URL: str = "https://storage.yandexcloud.net"
    S3_REGION: str = "ru-central1"

    # Yandex Cloud LLM
    YANDEX_CLOUD_API_KEY: str = Field(
        default="",
        validation_alias=AliasChoices(
            "YANDEX_CLOUD_API_KEY",
            "YANDEX_API_KEY",
            "YC_API_KEY",
        ),
    )
    YANDEX_CLOUD_FOLDER: str = Field(
        default="",
        validation_alias=AliasChoices(
            "YANDEX_CLOUD_FOLDER",
            "YANDEX_CLOUD_FOLDER_ID",
            "YANDEX_FOLDER_ID",
            "YC_FOLDER_ID",
            "FOLDER_ID",
        ),
    )
    YANDEX_REASONING_EFFORT: str = Field(
        default="high",
        validation_alias=AliasChoices(
            "YANDEX_REASONING_EFFORT",
            "YANDEX_GPT_REASONING_EFFORT",
            "REASONING_EFFORT",
        ),
    )
    ARTICLE_MODEL_ID: str = Field(
        default="deepseek-v32",
        validation_alias=AliasChoices("ARTICLE_MODEL_ID"),
    )
    TRANSLATION_MODEL_ID: str = Field(
        default="deepseek-v32",
        validation_alias=AliasChoices("TRANSLATION_MODEL_ID"),
    )
    TRANSLATION_REASONING_EFFORT: str = Field(
        default="low",
        validation_alias=AliasChoices("TRANSLATION_REASONING_EFFORT"),
    )
    YANDEX_CLIENT_ID: str = ""
    YANDEX_CLIENT_SECRET: str = ""
    YANDEX_OAUTH_SCOPES: str = "login:email login:info login:avatar"
    GITHUB_CLIENT_ID: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GITHUB_CLIENT_ID",
            "CLIENT_GIT",
        ),
    )
    GITHUB_CLIENT_SECRET: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GITHUB_CLIENT_SECRET",
            "CLIENT_GIT_SECRET",
        ),
    )
    GITHUB_OAUTH_SCOPES: str = "read:user user:email"
    # Explicit public base URL of this backend instance (e.g. https://api.hacknet.tech).
    # When set, all OAuth callback URLs are built from this value instead of
    # being derived from the incoming request's Host header.
    BACKEND_CALLBACK_BASE_URL: str = ""
    TELEGRAM_BOT_API_TOKEN: str = Field(
        default="",
        validation_alias=AliasChoices(
            "TELEGRAM_BOT_API_TOKEN",
            "TG_BOT_API_TOKEN",
        ),
    )
    TELEGRAM_CLIENT_ID: str = Field(
        default="",
        validation_alias=AliasChoices(
            "TELEGRAM_CLIENT_ID",
            "TG_CLIENT_ID",
        ),
    )
    TELEGRAM_CLIENT_SECRET: str = Field(
        default="",
        validation_alias=AliasChoices(
            "TELEGRAM_CLIENT_SECRET",
            "TG_CLIENT_SECRET",
        ),
    )
    TELEGRAM_OAUTH_SCOPES: str = "openid profile"
    YANDEX_MAIL_LOGIN: str = ""
    YANDEX_MAIL_PASSWORD: str = ""
    SMTP_HOST: str = "smtp.yandex.ru"
    SMTP_PORT: int = 465
    SMTP_USE_SSL: bool = True
    SMTP_FROM: str = ""
    MAGIC_LINK_TTL_HOURS: int = 24
    PASSWORD_RESET_TOKEN_TTL_MINUTES: int = 60
    PASSWORD_RESET_REQUEST_RATE_LIMIT_COUNT: int = 3
    PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW: int = 3600
    PASSWORD_RESET_CONFIRM_RATE_LIMIT_COUNT: int = 5
    PASSWORD_RESET_CONFIRM_RATE_LIMIT_WINDOW: int = 60
    PROMPTS_DIR: str = ""

    # AI Generator (GRPO pipeline)
    AI_GEN_NUM_VARIANTS: int = 5
    AI_GEN_MAX_RETRIES: int = 2
    AI_GEN_MIN_REWARD_THRESHOLD: float = 0.6
    AI_GEN_BASE_TEMPERATURE: float = 0.7
    AI_GEN_TEMPERATURE_STEP: float = 0.1
    AI_GEN_RAG_CONTEXT_LIMIT: int = 5
    AI_GEN_REQUIRE_RAG: bool = True
    AI_GEN_EMBEDDING_DIMENSION: int = 256
    AI_GEN_EMBEDDING_MAX_CHARS: int = 3500

    class Config:
        # Support both backend/.env and repo-root .env for local/prod parity.
        env_file = (ENV_FILE_PATH, ROOT_ENV_FILE_PATH)
        extra = "ignore"

    @field_validator("CORS_ALLOW_METHODS", "CORS_ALLOW_HEADERS", mode="before")
    @classmethod
    def parse_cors_list(cls, value: Any) -> Any:
        return cls._parse_list(value)

    @staticmethod
    def _parse_list(value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return []
            if value.startswith("["):
                try:
                    parsed = json.loads(value)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass
            return [item.strip() for item in value.split(",") if item.strip()]
        return [str(value).strip()] if str(value).strip() else []

    @field_validator("CORS_ALLOW_ORIGIN_REGEX", mode="before")
    @classmethod
    def normalize_optional_regex(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator(
        "YANDEX_CLOUD_API_KEY",
        "YANDEX_CLOUD_FOLDER",
        "YANDEX_CLIENT_ID",
        "YANDEX_CLIENT_SECRET",
        "YANDEX_OAUTH_SCOPES",
        "GITHUB_CLIENT_ID",
        "GITHUB_CLIENT_SECRET",
        "GITHUB_OAUTH_SCOPES",
        "BACKEND_CALLBACK_BASE_URL",
        "TELEGRAM_BOT_API_TOKEN",
        "TELEGRAM_CLIENT_ID",
        "TELEGRAM_CLIENT_SECRET",
        "TELEGRAM_OAUTH_SCOPES",
        "YANDEX_MAIL_LOGIN",
        "YANDEX_MAIL_PASSWORD",
        "SMTP_HOST",
        "SMTP_FROM",
        "PROMPTS_DIR",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @field_validator("YANDEX_REASONING_EFFORT", mode="before")
    @classmethod
    def normalize_reasoning_effort(cls, value: Any) -> str:
        normalized = "high" if value is None else str(value).strip().lower()
        if not normalized:
            normalized = "high"
        allowed = {"none", "low", "medium", "high"}
        if normalized not in allowed:
            raise ValueError(
                "YANDEX_REASONING_EFFORT must be one of: none, low, medium, high"
            )
        return normalized

    @field_validator("TRANSLATION_REASONING_EFFORT", mode="before")
    @classmethod
    def normalize_translation_reasoning_effort(cls, value: Any) -> str:
        normalized = "low" if value is None else str(value).strip().lower()
        if not normalized:
            normalized = "low"
        allowed = {"none", "low", "medium", "high"}
        if normalized not in allowed:
            raise ValueError(
                "TRANSLATION_REASONING_EFFORT must be one of: none, low, medium, high"
            )
        return normalized

    @field_validator("TRANSLATION_MODEL_ID", "ARTICLE_MODEL_ID", mode="before")
    @classmethod
    def normalize_model_ids(cls, value: Any) -> str:
        if value is None:
            return "deepseek-v32"
        normalized = str(value).strip()
        return normalized if normalized else "deepseek-v32"

    @field_validator("REFRESH_TOKEN_COOKIE_SAMESITE", mode="before")
    @classmethod
    def normalize_cookie_samesite(cls, value: Any) -> str:
        normalized = "lax" if value is None else str(value).strip().lower()
        if normalized not in {"lax", "strict", "none"}:
            raise ValueError("REFRESH_TOKEN_COOKIE_SAMESITE must be one of: lax, strict, none")
        return normalized

    @field_validator("REFRESH_TOKEN_COOKIE_DOMAIN", mode="before")
    @classmethod
    def normalize_cookie_domain(cls, value: Any) -> str:
        if value is None:
            return ""
        return str(value).strip()

    @property
    def cors_allow_origins(self) -> list[str]:
        return self._parse_list(self.CORS_ALLOW_ORIGINS)
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    @property
    def s3_task_bucket_name(self) -> str:
        explicit = (self.S3_TASK_BUCKET_NAME or "").strip()
        if explicit:
            return explicit
        return (self.S3_BUCKET_NAME or "").strip()

    @property
    def s3_task_access_key(self) -> str:
        return (self.S3_ACCESS_KEY or "").strip()

    @property
    def s3_task_secret_key(self) -> str:
        return (self.S3_SECRET_KEY or "").strip()

    @property
    def refresh_token_expire_seconds(self) -> int:
        return int(self.REFRESH_TOKEN_EXPIRE_HOURS) * 60 * 60

    @property
    def smtp_from_address(self) -> str:
        explicit = (self.SMTP_FROM or "").strip()
        if explicit:
            return explicit
        return (self.YANDEX_MAIL_LOGIN or "").strip()

settings = Settings()
