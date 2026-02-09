from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from app.config import settings

# Движок для подключения к БД
# SQL echo включается только через env (SQL_ECHO=true) для безопасного prod-default.
engine = create_async_engine(
    settings.database_url,
    echo=settings.SQL_ECHO,
    future=True,
    # Serverless containers may reuse stale TCP connections between requests.
    # pre_ping checks liveness and transparently reconnects.
    pool_pre_ping=True,
    # Recycle pooled connections periodically to reduce "connection is closed" errors
    # from upstream idle timeouts (PG/pgbouncer/network).
    pool_recycle=300,
)

# Фабрика для создания сессий (сессия = временное подключение к БД)
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False  # Объекты остаются доступными после commit
)

# Базовый класс для всех моделей (таблиц)
Base = declarative_base()

# Функция для получения сессии БД (используем в API)
async def get_db():
    """
    Создает сессию БД для каждого запроса.
    После выполнения запроса - закрывает сессию.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session  # Отдаем сессию в endpoint
        finally:
            await session.close()  # Закрываем после использования
