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
    ALGORITHM: str = "HS256"  # Алгоритм шифрования токенов
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30  # Токен живет 30 минут
    
    class Config:
        env_file = ".env"  # Откуда читать настройки
    
    @property
    def database_url(self) -> str:
        """
        Создает строку подключения к БД
        Формат: postgresql+asyncpg://user:password@host:port/database
        """
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

# Создаем объект настроек (используем везде в приложении)
settings = Settings()