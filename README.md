# HackNet Platform

Платформа для обучения кибербезопасности в формате CTF (Capture The Flag). Пользователи решают задачи, участвуют в чемпионатах, изучают базу знаний CVE и проходят обучающие курсы. AI-генерация задач на основе YandexGPT.

**Продакшн:** [hacknet.tech](https://www.hacknet.tech/)

---

## Содержание

- [Что умеет платформа](#что-умеет-платформа)
- [Стек технологий](#стек-технологий)
- [Структура репозитория](#структура-репозитория)
- [Backend](#backend)
- [Frontend](#frontend)
- [База данных](#база-данных)
- [Аутентификация](#аутентификация)
- [AI-пайплайн](#ai-пайплайн)
- [Запуск локально](#запуск-локально)
- [Тесты](#тесты)
- [Сборка и деплой](#сборка-и-деплой)
- [Конвенции](#конвенции)
- [Документация](#документация)

---

## Что умеет платформа

| Модуль | Описание |
|---|---|
| **CTF-задачи** | Задачи по категориям (web, crypto, forensics, reverse и др.). Типы доступа: VPN, VM, ссылка, файл, чат с AI, просто флаг |
| **Чемпионаты** | Соревнования с таблицей рейтинга, командной игрой и системой сабмитов |
| **База знаний** | Статьи по CVE/CWE, синхронизация с NVD, embeddings для поиска |
| **Обучение** | Задачи. Прогресс на пользователя |
| **AI-генерация** | GRPO-пайплайн генерирует 5 вариантов задачи, отбирает лучший по reward-модели |
| **Чат-задачи** | Интерактивные задачи в диалоге с LLM (YandexGPT) |
| **Рейтинг** | Глобальная таблица лидеров с фильтрами |
| **Тарифы** | FREE / PRO / CORP. Первые 1000 пользователей получают промо через DB-триггер |
| **Админка** | Управление задачами, конкурсами, промптами, NVD-синком |

---

## Стек технологий

### Backend
- **Python 3.11** + **FastAPI 0.128** — async REST API
- **SQLAlchemy 2.0** (async) + **asyncpg** — ORM поверх PostgreSQL
- **pgvector** — векторный поиск по embeddings (256-dim)
- **Redis** — распределённый rate-limit, кэш сессий
- **JWT** — 15-мин access tokens + 48-ч rotating HttpOnly refresh tokens
- **Yandex Cloud Object Storage** — S3-совместимое хранилище (boto3)
- **OpenAI SDK 2.11** (с Yandex LLM endpoint) — генерация задач и чат

### Frontend
- **React 19** (Create React App)
- **React Router DOM 7** — hash-based роутинг (совместимость с S3 static hosting)
- **Axios 1.13** — HTTP-клиент с response caching и авто-обновлением токенов
- **Tailwind CSS v4**

### Инфраструктура (Yandex Cloud)
- **Managed PostgreSQL** — `yandexcloud`
- **Managed Redis**
- **Object Storage** — `storage.yandexcloud.net`
- **Yandex LLM API** — YandexGPT для генерации задач и статей


---

## Структура репозитория

```
unistartup/
├── backend/                    FastAPI-приложение
│   ├── app/                    Основной код
│   │   ├── main.py             Точка входа, CORS, middleware, роутеры
│   │   ├── config.py           Настройки через pydantic-settings
│   │   ├── database.py         Async SQLAlchemy engine, session factory
│   │   ├── auth/               JWT-зависимости и security helpers
│   │   ├── models/             SQLAlchemy ORM-модели
│   │   ├── schemas/            Pydantic request/response схемы
│   │   ├── routes/             HTTP-эндпоинты (по модулям)
│   │   ├── services/           Бизнес-логика
│   │   ├── security/           Rate limiting, audit log, заголовки
│   │   ├── scripts/            Разовые скрипты (migrations, backfill)
│   │   └── prompts/            Шаблоны промптов в коде
│   ├── migrations/             Миграции БД
│   ├── Dockerfile              Образ для деплоя (port 8080)
│   ├── requirements.txt        Python-зависимости
│   └── .env.example            Шаблон переменных окружения
├── frontend/                   React SPA
│   ├── src/
│   │   ├── App.js              Роутер, protected routes
│   │   ├── pages/              Страницы приложения
│   │   ├── components/         Общие компоненты (Layout, Header, Sidebar)
│   │   └── services/api.js     Axios instance с token refresh
│   └── package.json
├── schema.sql                  Полная схема БД (референс)
├── docs/                       Дополнительная документация
├── .github/workflows/          CI/CD
├── DEPLOYMENT_GUIDE.md         Инструкция по деплою на Yandex Cloud
├── SECURITY_REPORT.md          Отчёт по безопасности
└── AI_PIPELINE_METRICS_GUIDE.md  Метрики AI-пайплайна
```

---

## Backend

### Маршруты (`backend/app/routes/`)

| Файл | Что делает |
|---|---|
| `auth.py` | Логин, логаут, OAuth (Yandex, GitHub, Telegram), refresh токенов |
| `auth_registration.py` | Регистрация, верификация email, magic link, сброс пароля |
| `pages.py` | Публичные страницы и CMS-контент (самый объёмный роутер) |
| `education.py` | Курсы, модули, уроки, задачи, прогресс пользователя |
| `contests.py` | Чемпионаты: создание, участие, сабмиты, рейтинг |
| `profile.py` | Профиль пользователя, аватар, настройки |
| `ratings.py` | Таблица лидеров |
| `knowledge.py` | База знаний CVE/CWE, статьи |
| `ai_generate.py` | Запуск AI-генерации задач, статус пайплайна |
| `user_variants.py` | Персональные варианты задач на пользователя |
| `feedback.py` | Обратная связь |
| `cron.py` | Внутренние cron-эндпоинты |

### Ключевые сервисы (`backend/app/services/`)

| Файл | Что делает |
|---|---|
| `ai_generator/pipeline.py` | GRPO-пайплайн генерации задач (5 вариантов → отбор по reward) |
| `ai_generator/reward.py` | Reward-модель для оценки качества сгенерированных задач |
| `ai_generator/rag_context.py` | RAG: поиск релевантного контекста через pgvector embeddings |
| `task_generation.py` | Оркестратор генерации CTF-задач |
| `article_generation.py` | AI-генерация статей базы знаний |
| `chat_task.py` | Интерактивные чат-задачи с LLM |
| `nvd_sync.py` | Синхронизация CVE-данных из NVD |
| `prompt_loader.py` | Загрузка промптов из БД (редактируются через админку) |
| `auth_sessions.py` | Управление сессиями и refresh-токенами |
| `registration.py` | Логика регистрации, верификации, OAuth-привязки |
| `activity_logger.py` | Лог действий пользователя |
| `championship_generation.py` | Генерация задач для чемпионатов |
| `championship_job_runner.py` | Фоновый запуск и мониторинг заданий чемпионата |
| `storage.py` | Работа с Yandex Object Storage (S3) |
| `daily_pipeline.py` | Ежедневный пайплайн: NVD-синк, эмбеддинги, перевод |

---

## Frontend

### Страницы (`frontend/src/pages/`)

| Страница | Путь | Описание |
|---|---|---|
| `Welcome` | `/` | Лендинг для неавторизованных |
| `Home` | `/#/home` | Главная: задачи, фильтры, поиск |
| `Education` | `/#/education` | Список курсов |
| `EducationTask` | `/#/education/:id` | Урок с задачей |
| `Knowledge` | `/#/knowledge` | База знаний CVE |
| `KnowledgeArticle` | `/#/knowledge/:id` | Статья CVE/CWE |
| `Championship` | `/#/championship` | Список чемпионатов |
| `Rating` | `/#/rating` | Таблица лидеров |
| `Profile` | `/#/profile` | Профиль пользователя |
| `Admin` | `/#/admin` | Панель администратора |
| `Pipeline` | `/#/pipeline` | Мониторинг AI-пайплайна |
| `CvePipeline` | `/#/cve-pipeline` | NVD-синк и CVE-обработка |
| `UserTaskVariants` | `/#/variants` | Персональные варианты задач |
| `Login` / `Register` | `/#/login` / `/#/register` | Аутентификация |

Используется **HashRouter** — необходим для корректной работы S3 static hosting (нет серверного роутинга).

### API-клиент (`frontend/src/services/api.js`)

Axios instance с:
- Автоматическим обновлением access token через refresh cookie
- Response caching (GET-запросы)
- Перехватом 401 → редирект на `/login`

---

## База данных

Полная схема: [`schema.sql`](schema.sql) и [`backend/current_schema.sql`](backend/current_schema.sql).

### Группы таблиц

| Группа | Таблицы |
|---|---|
| **Пользователи и авторизация** | `users`, `user_profiles`, OAuth-идентификаторы (Yandex/GitHub/Telegram), refresh tokens, magic links, сброс пароля |
| **Задачи** | `tasks`, `task_flags`, `task_materials` — доступ: vpn/vm/link/file/chat/just_flag |
| **Чат-задачи** | `task_chat_sessions`, `task_chat_messages` |
| **Чемпионаты** | `contests`, `contest_tasks`, `contest_participants`, `submissions` |
| **Обучение** | `courses`, `course_modules`, `lessons`, `lesson_tasks` |
| **Варианты задач** | `user_task_variants` — персональные варианты на пользователя |
| **База знаний** | `kb_entries`, `kb_comments`, `nvd_sync_log` |
| **Рейтинг** | `user_ratings`, rollup-таблицы |
| **Тарифы** | `tariff_plans`, `user_tariffs` — FREE/PRO/CORP; DB-триггер: первые 1000 → промо |
| **AI** | `llm_generations` (лог), `prompt_templates` (редактируемые промпты) |
| **Embeddings** | pgvector — 256-dim, используется в RAG для kb_entries |
| **Аудит** | `audit_logs` — лог действий, security events |

---

## Аутентификация

```
POST /auth/login
  → access_token (15 мин, localStorage)
  + refresh_token (48 ч, HttpOnly cookie, rotating)

POST /auth/refresh
  → новый access_token + новый refresh_token (старый инвалидируется)

OAuth: Yandex / GitHub / Telegram
  → callback → привязка к users → те же JWT
```

- Защищённые роуты требуют `Depends(get_current_user)` из `backend/app/auth/dependencies.py`
- Фронтенд авто-обновляет токен перед истечением через axios interceptor

---

## AI-пайплайн

### Генерация задач (GRPO)

```
Входные данные: тема, категория, сложность
    ↓
Генерация 5 вариантов задачи (YandexGPT / OpenAI-compatible endpoint)
    ↓
Reward-модель оценивает каждый вариант (threshold: 0.6)
    ↓
Лучший вариант → создание задачи + артефактов (файлы, флаги)
    ↓
Сохранение в llm_generations (аудит)
```

Файлы пайплайна: `services/ai_generator/pipeline.py`, `reward.py`, `artifact_creator.py`

### RAG-контекст

- Embeddings хранятся в pgvector (256-dim)
- При генерации задачи → поиск похожих CVE/статей → добавляется в промпт
- `services/ai_generator/rag_context.py`

### Промпты

Хранятся в таблице `prompt_templates` и редактируются через админку без деплоя. `services/prompt_loader.py` загружает их из БД.

---

## Запуск локально

### Backend

```bash
cd backend

# Создать и активировать venv
python3.11 -m venv .venv && source .venv/bin/activate

# Установить зависимости
pip install -r requirements.txt

# Скопировать и заполнить .env
cp .env.example .env
# Заполнить: DB_*, SECRET_KEY, S3_*, YANDEX_CLOUD_API_KEY, YANDEX_CLOUD_FOLDER

# Запустить сервер
python -m uvicorn app.main:app --reload --port 8000
```

API доступен на `http://localhost:8000`. Swagger: `http://localhost:8000/docs`.

### Frontend

```bash
cd frontend
npm install --legacy-peer-deps

# Подключиться к локальному backend
REACT_APP_API_BASE_URL=http://localhost:8000 npm start
```

Откроется на `http://localhost:3000`.

### Переменные окружения

Все переменные с описанием: [`backend/.env.example`](backend/.env.example)

Ключевые:

| Переменная | Описание |
|---|---|
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | PostgreSQL (порт 6432 = PgBouncer) |
| `SECRET_KEY` | JWT-секрет (обязательно, длинный случайный) |
| `S3_ENDPOINT` / `S3_BUCKET` / `S3_ACCESS_KEY` / `S3_SECRET_KEY` | Yandex Object Storage |
| `YANDEX_CLOUD_API_KEY` / `YANDEX_CLOUD_FOLDER` | LLM API |
| `REDIS_URL` | Redis для rate limiting |
| `REACT_APP_API_BASE_URL` | (frontend) URL backend API |

---

## Тесты

```bash
# Frontend
cd frontend
npm test
```

Frontend-тесты: `Login.test.js`, `Profile.test.js`, `Register.test.js`.

---

## Сборка и деплой

### Docker (backend)

```bash
cd backend
docker build -t hacknet-backend .
docker run -p 8080:8080 --env-file .env hacknet-backend
```

Dockerfile: `python:3.11-slim`, uvicorn на порту **8080**, `app.main:app`.

### Frontend (S3 static hosting)

```bash
cd frontend
REACT_APP_API_BASE_URL=https://api.hacknet.tech npm run build
# Загрузить содержимое build/ в Yandex Object Storage bucket
```

### Yandex Cloud

Полная инструкция по деплою: **[DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)**

Продакшн-ресурсы:
- Managed PostgreSQL → `mdb.yandexcloud.net:6432` (PgBouncer)
- Managed Redis
- Object Storage: медиафайлы + статика фронтенда
- Домены: `hacknet.tech` (SPA), `api.hacknet.tech` (backend)

### CI/CD

GitHub Actions: `.github/workflows/`

---

## Конвенции

| Правило | Значение |
|---|---|
| DB-порт | **6432** (PgBouncer, не прямой PostgreSQL) |
| Временны́е метки | `TIMESTAMPTZ` везде |
| Медленный запрос | ≥ 1000 ms → логируется в `X-Process-Time-Ms` |
| Startup DB maintenance | Отключён по умолчанию (`RUN_STARTUP_DB_MAINTENANCE=false`) |
| HashRouter | Обязателен для S3 (нет server-side routing) |
| Промпты | Редактируются в БД через админку, не хардкодятся |
| Embeddings | 256-dim (`AI_GEN_EMBEDDING_DIMENSION=256`) |
| GRPO reward threshold | 0.6 (задача принимается если reward ≥ 0.6) |

---

## Документация

| Файл | Содержимое |
|---|---|
| [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md) | Пошаговый деплой на Yandex Cloud |
| [`SECURITY_REPORT.md`](SECURITY_REPORT.md) | Анализ безопасности платформы |
| [`AI_PIPELINE_METRICS_GUIDE.md`](AI_PIPELINE_METRICS_GUIDE.md) | Метрики и мониторинг AI-пайплайна |
| [`docs/`](docs/) | Дополнительные материалы |

---

## Лицензия

[LICENSE](LICENSE)
