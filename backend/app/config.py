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
    
    @property
    def database_url(self) -> str:
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
