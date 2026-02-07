import json
from typing import Any, Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings

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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    SQL_ECHO: bool = False

    # CORS
    CORS_ALLOW_ORIGINS: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "https://storage.yandexcloud.net"
    )
    CORS_ALLOW_ORIGIN_REGEX: Optional[str] = (
        r"^https://[a-zA-Z0-9-]+\.website\.yandexcloud\.net$"
    )
    CORS_ALLOW_CREDENTIALS: bool = False
    CORS_ALLOW_METHODS: list[str] = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
    CORS_ALLOW_HEADERS: list[str] = ["Authorization", "Content-Type", "X-Auth-Token"]
    
    # Yandex Object Storage (S3-совместимое хранилище)
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_BUCKET_NAME: str = ""
    S3_ENDPOINT_URL: str = "https://storage.yandexcloud.net"
    S3_REGION: str = "ru-central1"

    # Yandex Cloud LLM
    YANDEX_CLOUD_API_KEY: str = ""
    YANDEX_CLOUD_FOLDER: str = ""
    
    class Config:
        env_file = ".env"
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

    @property
    def cors_allow_origins(self) -> list[str]:
        return self._parse_list(self.CORS_ALLOW_ORIGINS)
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
