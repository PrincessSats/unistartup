# Hermes Agent Project Guide

## Repository Context

- **Repository name**: unistartup (root directory name)
- **Project name**: HackNet Platform
- **Location**: `/Users/mmms/Developer/unistartup`
- **Related files**: CLAUDE.md, CODEX.md, GEMINI.md, QWEN.md (AI assistant guides)
- **Primary documentation**: CLAUDE.md (detailed project overview and conventions)

## Project Overview

HackNet Platform is a cybersecurity CTF (Capture The Flag) learning platform where users solve security challenges, participate in contests, and study vulnerability knowledge base articles. Deployed on Yandex Cloud.

## Tech Stack

### Backend (`/backend`)
- **Python 3.11 + FastAPI** — async REST API
- **PostgreSQL** — via `asyncpg` + SQLAlchemy 2.0 async (port 6432 with PgBouncer)
- **JWT auth** — 15-min access tokens + 48-hour rotating HttpOnly refresh tokens
- **Yandex Cloud Object Storage** — S3-compatible file storage
- **Yandex Cloud LLM (YandexGPT) + OpenAI SDK** — AI task generation and chat challenges
- **Additional services**: task generation, article generation, chat tasks, NVD sync, prompt loader, AI generator pipeline (GRPO), registration, activity logging, audit logging, security headers, rate limiting, input sanitization

### Frontend (`/frontend`)
- **React 19** (Create React App)
- **React Router DOM v7** — hash-based routing (for S3 static hosting)
- **Axios** — HTTP client with response caching and token refresh
- **Tailwind CSS v4**

## Architecture

### Backend Structure
```
backend/app/
  main.py          — FastAPI app, CORS, middleware, router registration
  config.py        — Settings via pydantic-settings (.env)
  database.py      — Async SQLAlchemy engine, session factory
  routes/          — auth, auth_registration, pages, profile, contests, ratings, feedback, knowledge, education, ai_generate, user_variants
  services/        — task_generation, article_generation, chat_task, nvd_sync, storage, prompt_loader, registration, activity_logger, ai_generator/* (rag_context, user_pipeline, prompt_safety, xss_utils, validator, reward, pipeline, feedback, cwe_mapping, artifact_creator, translation_service, reviewer, crypto_utils, forensics_utils, embedding_service)
  models/          — SQLAlchemy ORM models (users, profiles, ratings, tasks, contests, kb_entries, courses, audit_log, etc.)
  schemas/         — Pydantic request/response schemas
  auth/            — JWT and auth dependencies
  security/        — Rate limiting, security headers, input sanitization, audit logger
  prompts/         — Text prompts for AI generators (xss, forensics, crypto)
  scripts/         — DB maintenance, migration, backlog generation, metrics report
  migrations/      — SQL migration scripts
```

### Frontend Structure
```
frontend/src/
  App.js           — Router with protected routes
  pages/           — Home, Login, Register, Profile, Championship, Education, Knowledge, Rating, Admin, CvePipeline, Pipeline, ResetPassword, AuthBridge, EducationTask, KnowledgeArticle
  components/      — Layout, Header, Sidebar, modals, icons (Header, Layout, AppIcon, LoadingState, AppIllustration, HomeOnboardingOverlay, MobileBlock, AuthUI, TariffPlans, Sidebar, HacknetLogo, ContestCreateModal, FeedbackModal)
  services/api.js  — Axios instance with caching, token management, refresh logic
  utils/           — educationVisuals, knowledgeVisuals, chatInput
```

### Key Services
- **task_generation.py** — LLM-powered CTF task creation
- **article_generation.py** — AI article generation for knowledge base
- **chat_task.py** — Interactive LLM chat challenges
- **nvd_sync.py** — NVD (National Vulnerability Database) sync for CVE data
- **prompt_loader.py** — Database-stored editable prompts for LLM
- **ai_generator pipeline** — GRPO-based AI pipeline for generating task variants, with RAG context, reward modeling, validation, and safety checks
- **registration.py** — User registration with email verification and promo tariff assignment (first 1000 users get PRO plan)
- **activity_logger.py** — User activity tracking
- **storage.py** — Yandex S3 integration for task materials
- **security modules** — rate limiting, input sanitization, security headers, audit logging

### Database Schema (`/schema.sql`)
Key tables:
- `users`, `user_profiles`, `user_ratings` — auth and user data
- `tariff_plans`, `user_tariffs` — FREE/PRO/CORP subscriptions (first 1000 get promo via trigger)
- `tasks`, `task_flags`, `task_materials` — CTF challenges (access types: vpn, vm, link, file, chat, just_flag)
- `task_chat_sessions`, `task_chat_messages` — LLM interactive challenges
- `contests`, `contest_tasks`, `contest_participants`, `submissions` — competitive mode
- `kb_entries`, `kb_comments`, `nvd_sync_log` — CVE knowledge base
- `courses`, `course_modules`, `lessons`, `lesson_tasks` — educational content
- `llm_generations`, `prompt_templates` — LLM audit log and prompt management
- `audit_logs`, `auth_refresh_tokens`, `auth_password_reset_tokens`, `user_auth_identities` — security and auth
- `user_task_variants` — AI-generated task variants
- `feedback` — user feedback

Extensions: `btree_gist`, `vector` (for embeddings)

## Key Conventions

- DB port: **6432** (PgBouncer)
- All timestamps: `TIMESTAMPTZ`
- Slow request threshold: 1000ms (logs via `X-Process-Time-Ms` header)
- Startup DB maintenance: disabled by default (`RUN_STARTUP_DB_MAINTENANCE=false`)
- Production domain: `hacknet.tech`
- Frontend uses HashRouter for S3 static hosting compatibility
- CORS configured for localhost, production domains, and Yandex Cloud storage
- Refresh tokens stored as HttpOnly cookies, access tokens in localStorage
- AI generator pipeline uses GRPO (Group Relative Policy Optimization) with temperature stepping, reward threshold, and RAG context

## Authentication Flow

1. Login returns access token (localStorage) + refresh token (HttpOnly cookie)
2. Access tokens expire in 15 min; refresh tokens rotate on use (48h lifetime)
3. Frontend auto-refreshes tokens before expiry via axios interceptor
4. Protected routes redirect to `/login` when unauthenticated
5. OAuth providers: Yandex, GitHub, Telegram (optional)
6. Password reset tokens with rate limiting

## Environment Variables

### Backend (`.env`)
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `SECRET_KEY` — JWT secret (required)
- `S3_*` — Yandex S3 credentials
- `YANDEX_CLOUD_API_KEY`, `YANDEX_CLOUD_FOLDER` — LLM access
- `YANDEX_REASONING_EFFORT` — AI reasoning effort (disabled/low/medium/high)
- `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` — OAuth
- `TELEGRAM_BOT_API_TOKEN`, `TELEGRAM_CLIENT_ID`, `TELEGRAM_CLIENT_SECRET` — Telegram OAuth
- `YANDEX_MAIL_LOGIN`, `YANDEX_MAIL_PASSWORD` — SMTP for email
- `BACKEND_CALLBACK_BASE_URL` — OAuth callback base URL
- `PROMPTS_DIR` — directory for AI prompts
- AI generator settings: `AI_GEN_NUM_VARIANTS`, `AI_GEN_MAX_RETRIES`, `AI_GEN_MIN_REWARD_THRESHOLD`, `AI_GEN_BASE_TEMPERATURE`, `AI_GEN_TEMPERATURE_STEP`, `AI_GEN_RAG_CONTEXT_LIMIT`, `AI_GEN_EMBEDDING_DIMENSION`

### Frontend
- `REACT_APP_API_BASE_URL` — Backend URL (required for build)
- `REACT_APP_API_TIMEOUT_MS` — Request timeout (default 15000)
- `REACT_APP_ADMIN_NVD_TIMEOUT_MS` — Admin NVD sync timeout (default 120000)
- `REACT_APP_AUTH_LOGIN_TIMEOUT_MS` — Auth login timeout (default 10000)
- `REACT_APP_AUTH_REFRESH_TIMEOUT_MS` — Auth refresh timeout (default REQUEST_TIMEOUT_MS)

## Commands

### Backend
```bash
cd backend
pip install -r requirements.txt

# Run development server
python -m uvicorn app.main:app --reload --port 8000

# Run tests
python -m unittest discover -s tests -p "test_*.py"

# Run DB maintenance (for deployment)
python -m app.scripts.db_maintenance

# Run migration
python -m app.scripts.run_migration add_security_enhancements
```

### Frontend
```bash
cd frontend
npm install --legacy-peer-deps

# Run development server (connects to localhost:8000)
REACT_APP_API_BASE_URL=http://localhost:8000 npm start

# Run tests
npm test

# Build for production
REACT_APP_API_BASE_URL=<api-url> npm run build
```

## Deployment

- Primary production environment: **Yandex Cloud**
- Backend deployed as serverless containers or VM
- Frontend hosted on Yandex Object Storage (S3) with static website hosting
- Database: Yandex Managed PostgreSQL with PgBouncer (port 6432)
- Security: HSTS, CSP, rate limiting, audit logging, input sanitization
- See `DEPLOYMENT_GUIDE.md` for detailed steps

## AI/ML Components

- **YandexGPT integration** for task generation, article generation, and chat challenges
- **AI Generator pipeline** (GRPO) for creating diverse task variants with safety validation
- **RAG context** retrieves relevant knowledge base articles for AI generation
- **Embedding service** for semantic search (vector extension)
- **Prompt management** via database-stored templates

## Security Features

- Rate limiting per endpoint and IP
- Input sanitization (HTML, SQL, XSS filters)
- Security headers (HSTS, CSP, X-Frame-Options, etc.)
- Audit logging of security events (failed logins, XSS attempts, SQL injection attempts)
- Password policy enforcement
- Refresh token rotation and revocation
- OAuth2 with state validation

## Development Notes

- Codebase uses Russian comments and variable names in some places
- Project root contains multiple AI assistant guides (CLAUDE.md, CODEX.md, GEMINI.md, QWEN.md)
- Design directory contains Figma snapshots and design assets
- `schema.sql` is the authoritative schema; migrations are additive
- `backend/migrations/` includes SQL scripts for incremental updates
- `backend/scripts/` includes utility scripts for maintenance and reporting

## Hermes Agent Integration

- Use `jCodemunch-MCP` tools for code exploration (per CLAUDE.md guidance)
- Always check for existing skills relevant to tasks (e.g., `github-pr-workflow`, `systematic-debugging`, `test-driven-development`)
- For backend changes, ensure compatibility with Yandex Cloud production environment
- For frontend changes, remember HashRouter and S3 static hosting constraints
- When dealing with AI generation, review prompt files in `backend/app/prompts/`
- Database changes should be applied via migrations, not direct schema edits

## Known Pitfalls

- DB port 6432 (PgBouncer) may cause connection issues if not configured correctly
- Refresh token cookie requires CORS credentials; ensure frontend origin is allowed
- Yandex Cloud LLM API key and folder ID must be set for AI features
- Frontend builds require `REACT_APP_API_BASE_URL` environment variable
- Early user promo trigger only applies to first 1000 verified users
- AI generator pipeline uses temperature stepping; may require tuning for quality

---
*Last updated: April 16, 2026*
*Based on analysis of repository structure, CLAUDE.md, config files, and schema.*