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
        "UPDATE users SET is_active = TRUE WHERE is_active IS NULL",
        "ALTER TABLE users ALTER COLUMN is_active SET DEFAULT TRUE",
        "ALTER TABLE users ALTER COLUMN is_active SET NOT NULL",
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
            last_login TIMESTAMPTZ,
            onboarding_status TEXT
        )
        """,
        "ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS onboarding_status TEXT",
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
        # Ротационные refresh-токены для 48h скользящей сессии.
        """
        CREATE TABLE IF NOT EXISTS auth_refresh_tokens (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            rotated_to_id BIGINT REFERENCES auth_refresh_tokens(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            last_used_at TIMESTAMPTZ,
            user_agent TEXT,
            ip_address TEXT
        )
        """,
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_auth_refresh_tokens_hash ON auth_refresh_tokens(token_hash)",
        "CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_active_user ON auth_refresh_tokens(user_id, revoked_at, expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_expires_at ON auth_refresh_tokens(expires_at)",
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


async def ensure_landing_hunt_schema_compatibility() -> None:
    """
    Создает таблицы и индексы для публичного hunt-механизма лендинга.
    Идемпотентно: безопасно вызывать на старте и при ручном обслуживании БД.
    """
    statements = [
        """
        CREATE TABLE IF NOT EXISTS landing_hunt_sessions (
            id BIGSERIAL PRIMARY KEY,
            session_token TEXT NOT NULL UNIQUE,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "ALTER TABLE landing_hunt_sessions ADD COLUMN IF NOT EXISTS completed_at TIMESTAMPTZ",
        "ALTER TABLE landing_hunt_sessions ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        "ALTER TABLE landing_hunt_sessions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_landing_hunt_sessions_token ON landing_hunt_sessions(session_token)",
        """
        CREATE TABLE IF NOT EXISTS landing_hunt_session_items (
            session_id BIGINT NOT NULL REFERENCES landing_hunt_sessions(id) ON DELETE CASCADE,
            bug_key TEXT NOT NULL,
            found_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (session_id, bug_key)
        )
        """,
        "ALTER TABLE landing_hunt_session_items ADD COLUMN IF NOT EXISTS found_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        "CREATE INDEX IF NOT EXISTS idx_landing_hunt_session_items_found_at ON landing_hunt_session_items(found_at DESC)",
        """
        CREATE TABLE IF NOT EXISTS promo_codes (
            id BIGSERIAL PRIMARY KEY,
            code TEXT NOT NULL UNIQUE,
            source TEXT NOT NULL,
            reward_points INTEGER NOT NULL DEFAULT 0,
            expires_at TIMESTAMPTZ NOT NULL,
            issued_hunt_session_id BIGINT UNIQUE REFERENCES landing_hunt_sessions(id) ON DELETE SET NULL,
            redeemed_by_user_id BIGINT REFERENCES users(id) ON DELETE SET NULL,
            redeemed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """,
        "ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'landing_hunt'",
        "ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS reward_points INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ",
        "ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS issued_hunt_session_id BIGINT",
        "ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS redeemed_by_user_id BIGINT",
        "ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS redeemed_at TIMESTAMPTZ",
        "ALTER TABLE promo_codes ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT now()",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_promo_codes_code ON promo_codes(code)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_promo_codes_issued_hunt_session_id ON promo_codes(issued_hunt_session_id)",
        "CREATE INDEX IF NOT EXISTS idx_promo_codes_source_expires_at ON promo_codes(source, expires_at)",
        "CREATE INDEX IF NOT EXISTS idx_promo_codes_redeemed_by_user_id ON promo_codes(redeemed_by_user_id)",
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_promo_codes_landing_redeemed_user_unique
        ON promo_codes(redeemed_by_user_id)
        WHERE source = 'landing_hunt' AND redeemed_by_user_id IS NOT NULL
        """,
    ]

    async with engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))
    logger.info("Landing hunt schema compatibility check completed")


async def ensure_performance_indexes() -> None:
    """
    Создает недостающие индексы для горячих запросов интерфейса.
    Идемпотентно: безопасно вызывается на каждом старте.
    """
    statements = [
        # Быстрые выборки карточек практики на главной и в каталоге.
        "CREATE INDEX IF NOT EXISTS idx_tasks_practice_ready_created ON tasks(task_kind, state, created_at DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_practice_ready_category_created ON tasks(task_kind, state, lower(category), created_at DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_practice_ready_difficulty_created ON tasks(task_kind, state, difficulty, created_at DESC, id DESC)",
        # Связанные сущности задач должны читаться по task_id без full scan.
        "CREATE INDEX IF NOT EXISTS idx_task_flags_task_id ON task_flags(task_id, id)",
        "CREATE INDEX IF NOT EXISTS idx_task_materials_task_id ON task_materials(task_id, id)",
        # Индексы для рейтингов/прогресса по сабмишенам.
        "CREATE INDEX IF NOT EXISTS idx_submissions_correct_contest_user_task ON submissions(contest_id, is_correct, user_id, task_id)",
        "CREATE INDEX IF NOT EXISTS idx_submissions_contest_correct_submitted ON submissions(contest_id, is_correct, submitted_at ASC, id ASC)",
        "CREATE INDEX IF NOT EXISTS idx_submissions_contest_user_correct ON submissions(contest_id, user_id, is_correct, submitted_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_submissions_correct_user_task_practice ON submissions(user_id, task_id) WHERE contest_id IS NULL AND is_correct = TRUE",
        "CREATE INDEX IF NOT EXISTS idx_submissions_practice_user_task_all ON submissions(user_id, task_id) WHERE contest_id IS NULL",
        "CREATE INDEX IF NOT EXISTS idx_submissions_practice_task_user_flag_correct ON submissions(task_id, user_id, flag_id) WHERE contest_id IS NULL AND is_correct = TRUE",
        # Быстрая сортировка общего рейтинга.
        "CREATE INDEX IF NOT EXISTS idx_user_ratings_contest_order ON user_ratings(contest_rating DESC, first_blood DESC, user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_ratings_practice_order ON user_ratings(practice_rating DESC, first_blood DESC, user_id)",
        "CREATE INDEX IF NOT EXISTS idx_user_profiles_username_lower ON user_profiles((lower(username)))",
        # Лента базы знаний сортируется по COALESCE(updated_at, created_at).
        "CREATE INDEX IF NOT EXISTS idx_kb_entries_updated_created_desc ON kb_entries((COALESCE(updated_at, created_at)) DESC)",
        # Итоги контестов часто читают участников в порядке входа.
        "CREATE INDEX IF NOT EXISTS idx_contest_participants_contest_joined ON contest_participants(contest_id, joined_at ASC)",
    ]

    async with engine.begin() as conn:
        for stmt in statements:
            await conn.execute(text(stmt))
    logger.info("Performance indexes check completed")
