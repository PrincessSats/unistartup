-- Расширение для GIST индексов
CREATE EXTENSION IF NOT EXISTS btree_gist;

-- 1. Пользователи (авторизация)
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    email           TEXT NOT NULL UNIQUE,
    password_hash   TEXT NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 2. Профили и роли
CREATE TABLE user_profiles (
    user_id     BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    username    TEXT NOT NULL UNIQUE,
    role        TEXT NOT NULL DEFAULT 'participant',  -- роли: 'admin', 'author', 'participant'
    bio         TEXT,
    avatar_url  TEXT,
    locale      TEXT DEFAULT 'ru-RU',
    timezone    TEXT DEFAULT 'Europe/Moscow',
    last_login  TIMESTAMPTZ
);

-- 3. Рейтинги (чемпионатный и практический)
CREATE TABLE user_ratings (
    user_id             BIGINT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    contest_rating      INTEGER NOT NULL DEFAULT 0,
    practice_rating     INTEGER NOT NULL DEFAULT 0,
    first_blood         INTEGER NOT NULL DEFAULT 0,
    last_updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3.1 Обратная связь
CREATE TABLE feedback (
    user_id     BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    topic       TEXT NOT NULL,
    message     TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Тарифные планы
CREATE TABLE tariff_plans (
    id                  BIGSERIAL PRIMARY KEY,
    code                TEXT NOT NULL UNIQUE, -- коды: 'FREE', 'PRO', 'CORP'
    name                TEXT NOT NULL,
    monthly_price_rub   NUMERIC(10,2) NOT NULL DEFAULT 0,
    description         TEXT,
    limits              JSONB DEFAULT '{}'::jsonb, -- туда можно сунуть лимиты по таскам/LLM и т.д.
    is_active           BOOLEAN NOT NULL DEFAULT TRUE
);

-- 5. Тарифы пользователей
CREATE TABLE user_tariffs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tariff_id       BIGINT NOT NULL REFERENCES tariff_plans(id),
    is_promo        BOOLEAN NOT NULL DEFAULT FALSE,  -- первые 1000 и т.п.
    source          TEXT,                            -- источник: 'early_1000', 'manual', 'corp_contract'
    valid_from      TIMESTAMPTZ NOT NULL DEFAULT now(),
    valid_to        TIMESTAMPTZ,                     -- NULL — текущий тариф
    CONSTRAINT user_tariffs_one_active
        EXCLUDE USING gist (
            user_id WITH =,
            tstzrange(valid_from, COALESCE(valid_to, 'infinity'::timestamptz)) WITH &&
    )
);
-- 4.2. База знаний по уязвимостям
CREATE TABLE kb_entries (
    id              BIGSERIAL PRIMARY KEY,
    source          TEXT NOT NULL,        -- источник: 'nvd', 'cve', 'blog', 'internal'
    source_id       TEXT,                 -- id в исходной системе
    cve_id          TEXT,                 -- например: CVE-2024-12345
    raw_en_text     TEXT,                 -- исходное описание
    ru_title        TEXT,
    ru_summary      TEXT,
    ru_explainer    TEXT,
    tags            TEXT[] DEFAULT '{}',  -- теги: ['web','xss','cve-2024-...']
    difficulty      INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_kb_entries_cve_id   ON kb_entries(cve_id);
CREATE INDEX idx_kb_entries_tags_gin ON kb_entries USING gin(tags);

-- 4.3. Комментарии к базе знаний
CREATE TABLE kb_comments (
    id              BIGSERIAL PRIMARY KEY,
    kb_entry_id     BIGINT NOT NULL REFERENCES kb_entries(id) ON DELETE CASCADE,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    parent_id       BIGINT REFERENCES kb_comments(id) ON DELETE CASCADE,
    body            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'published', -- статус: published|hidden|deleted|pending
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ,
    deleted_at      TIMESTAMPTZ
);

CREATE INDEX idx_kb_comments_entry_created ON kb_comments(kb_entry_id, created_at DESC);
CREATE INDEX idx_kb_comments_user_created ON kb_comments(user_id, created_at DESC);
CREATE INDEX idx_kb_comments_parent ON kb_comments(parent_id);

-- 4.4. Логи синхронизации NVD
CREATE TABLE nvd_sync_log (
    id              BIGSERIAL PRIMARY KEY,
    fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    window_start    TIMESTAMPTZ,
    window_end      TIMESTAMPTZ,
    inserted_count  INTEGER,
    status          TEXT NOT NULL DEFAULT 'success', -- статус: success|failed
    error           TEXT
);

CREATE INDEX idx_nvd_sync_log_fetched_at ON nvd_sync_log(fetched_at DESC);

-- 6. Задачи
CREATE TABLE tasks (
    id                      BIGSERIAL PRIMARY KEY,
    title                   TEXT NOT NULL,
    category                TEXT NOT NULL,       -- категории: 'web','pwn','crypto','re','forensics',...
    difficulty              INTEGER NOT NULL,    -- 1-10
    points                  INTEGER NOT NULL DEFAULT 100,
    tags                    TEXT[] DEFAULT '{}',
    language                TEXT NOT NULL DEFAULT 'ru',
    story                   TEXT,                -- сюжет
    participant_description TEXT,                -- текст для участника
    state                   TEXT NOT NULL DEFAULT 'draft', -- состояние: 'draft','ready','published','archived'
    kb_entry_id             BIGINT REFERENCES kb_entries(id),
    llm_raw_response        JSONB,
    created_by              BIGINT REFERENCES users(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_tasks_tags_gin ON tasks USING gin(tags);

-- 7. Флаги
CREATE TABLE task_flags (
    id              BIGSERIAL PRIMARY KEY,
    task_id         BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    flag_id         TEXT NOT NULL,   -- идентификатор: 'main','stage1','bonus'
    format          TEXT NOT NULL,   -- формат: 'FLAG{...}'
    expected_value  TEXT,            -- можно NULL на этапе черновика
    description     TEXT,
    UNIQUE (task_id, flag_id)
);

-- 8. Материалы задач
CREATE TABLE task_materials (
    id              BIGSERIAL PRIMARY KEY,
    task_id         BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    type            TEXT NOT NULL, -- тип: 'file','service','credentials','other'
    name            TEXT NOT NULL,
    description     TEXT,
    url             TEXT,          -- если это сервис или внешняя ссылка
    storage_key     TEXT           -- путь в object storage, если это файл
);

-- 9. Решение автора
CREATE TABLE task_author_solutions (
    task_id                 BIGINT PRIMARY KEY REFERENCES tasks(id) ON DELETE CASCADE,
    summary                 TEXT,
    steps                   JSONB,   -- список шагов решения
    difficulty_rationale    TEXT,
    implementation_notes    TEXT
);

-- 10. Чемпионаты
CREATE TABLE contests (
    id                  BIGSERIAL PRIMARY KEY,
    title               TEXT NOT NULL,
    description         TEXT,
    start_at            TIMESTAMPTZ NOT NULL,
    end_at              TIMESTAMPTZ NOT NULL,
    is_public           BOOLEAN NOT NULL DEFAULT FALSE,
    leaderboard_visible BOOLEAN NOT NULL DEFAULT TRUE
);

-- 11. Связка задач с чемпионатами
CREATE TABLE contest_tasks (
    contest_id      BIGINT NOT NULL REFERENCES contests(id) ON DELETE CASCADE,
    task_id         BIGINT NOT NULL REFERENCES tasks(id),
    order_index     INTEGER NOT NULL DEFAULT 0,
    points_override INTEGER,
    PRIMARY KEY (contest_id, task_id)
);

-- 12. Сабмишены
CREATE TABLE submissions (
    id              BIGSERIAL PRIMARY KEY,
    contest_id      BIGINT REFERENCES contests(id) ON DELETE CASCADE,
    task_id         BIGINT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    flag_id         TEXT NOT NULL,
    submitted_value TEXT NOT NULL,
    is_correct      BOOLEAN NOT NULL,
    awarded_points  INTEGER NOT NULL DEFAULT 0,
    submitted_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_submissions_user_contest ON submissions(user_id, contest_id);
-- 13. Курсы
CREATE TABLE courses (
    id              BIGSERIAL PRIMARY KEY,
    code            TEXT NOT NULL UNIQUE,  -- код: 'cyber-basic', 'python-101'
    title           TEXT NOT NULL,
    description     TEXT,
    level           TEXT,                  -- уровень: 'beginner','intermediate','advanced'
    is_public       BOOLEAN NOT NULL DEFAULT TRUE
);

-- 14. Модули внутри курса
CREATE TABLE course_modules (
    id              BIGSERIAL PRIMARY KEY,
    course_id       BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    title           TEXT NOT NULL,
    order_index     INTEGER NOT NULL DEFAULT 0
);

-- 15. Уроки
CREATE TABLE lessons (
    id                  BIGSERIAL PRIMARY KEY,
    course_id           BIGINT NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    module_id           BIGINT REFERENCES course_modules(id),
    title               TEXT NOT NULL,
    slug                TEXT,
    content             TEXT,       -- формат: markdown / html
    difficulty          INTEGER,
    estimated_minutes   INTEGER
);

-- 16. Привязка задач к урокам (практика)
CREATE TABLE lesson_tasks (
    lesson_id       BIGINT NOT NULL REFERENCES lessons(id) ON DELETE CASCADE,
    task_id         BIGINT NOT NULL REFERENCES tasks(id),
    order_index     INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (lesson_id, task_id)
);
-- 17. Логи генерации от моделей
CREATE TABLE llm_generations (
    id              BIGSERIAL PRIMARY KEY,
    model           TEXT NOT NULL,       -- модель: 'yandexgpt-lite', 'qwen', 'our-small-llm'
    purpose         TEXT NOT NULL,       -- назначение: 'task_generation','kb_explainer','feedback'
    input_payload   JSONB NOT NULL,      -- JSON-промпт
    output_payload  JSONB,               -- ответ модели
    kb_entry_id     BIGINT REFERENCES kb_entries(id),
    task_id         BIGINT REFERENCES tasks(id),
    created_by      BIGINT REFERENCES users(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_llm_generations_purpose ON llm_generations(purpose);
