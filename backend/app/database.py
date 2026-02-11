from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import logging
from app.config import settings

logger = logging.getLogger(__name__)

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


async def ensure_auth_schema_compatibility() -> None:
    """
    Приводит auth-подсхему к ожидаемому виду без отдельной миграционной системы.
    Нужен для старых БД, где таблица users могла быть создана без новых колонок.
    """
    statements = [
        # Базовая таблица пользователей.
        """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL
        )
        """,
        # Колонки, которые были добавлены позже.
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMPTZ",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        # Профили нужны для get_current_user (join с users).
        """
        CREATE TABLE IF NOT EXISTS user_profiles (
            user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            username TEXT NOT NULL UNIQUE,
            role TEXT NOT NULL DEFAULT 'participant',
            bio TEXT,
            avatar_url TEXT,
            locale TEXT DEFAULT 'ru-RU',
            timezone TEXT DEFAULT 'Europe/Moscow',
            last_login TIMESTAMPTZ
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_user_profiles_username ON user_profiles(username)",
        # Стартовые рейтинги используются на главной странице/профиле.
        """
        CREATE TABLE IF NOT EXISTS user_ratings (
            user_id BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            contest_rating INTEGER NOT NULL DEFAULT 0,
            practice_rating INTEGER NOT NULL DEFAULT 0,
            first_blood INTEGER NOT NULL DEFAULT 0,
            last_updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        # Обратная связь используется на главной и в хедере.
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            topic TEXT NOT NULL,
            message TEXT NOT NULL,
            resolved BOOLEAN NOT NULL DEFAULT FALSE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS id BIGSERIAL",
        "ALTER TABLE feedback ADD COLUMN IF NOT EXISTS resolved BOOLEAN NOT NULL DEFAULT FALSE",
        "CREATE INDEX IF NOT EXISTS idx_feedback_id ON feedback(id)",
        # Для legacy-пользователей, у которых ещё нет профиля/рейтинга.
        """
        INSERT INTO user_profiles (user_id, username, role)
        SELECT
            u.id,
            'legacy_' || u.id::text || '_' || substr(md5(u.email || ':' || u.id::text), 1, 8),
            'participant'
        FROM users u
        LEFT JOIN user_profiles p ON p.user_id = u.id
        WHERE p.user_id IS NULL
        ON CONFLICT DO NOTHING
        """,
        """
        INSERT INTO user_ratings (user_id)
        SELECT u.id
        FROM users u
        LEFT JOIN user_ratings r ON r.user_id = u.id
        WHERE r.user_id IS NULL
        ON CONFLICT DO NOTHING
        """,
    ]

    async with engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))
    logger.info("Auth schema compatibility check completed")
