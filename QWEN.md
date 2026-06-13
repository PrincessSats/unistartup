# qwen.md
Use short, 3-6 word sentences.
No filler, preamble, or pleasantries.
Run tools first, show the result, then stop. Do not narrate.
Drop articles ("Me fix code" not "I will fix the code").

# HackNet Platform — Project Overview
Always use jCodemunch-MCP tools — never fall back to Read, Grep, Glob, or Bash for code exploration.
- Before reading a file: use get_file_outline or get_file_content
- Before searching: use search_symbols or search_text
- Before exploring structure: use get_file_tree or get_repo_outline
- Call list_repos first; if the project is not indexed, call index_folder with the current directory.
## What is HackNet?

**HackNet** is a full-stack **cybersecurity CTF (Capture The Flag) learning platform** where users solve security challenges, participate in contests, and study vulnerability knowledge base articles. The platform is designed to teach practical cybersecurity skills through hands-on challenges.

**Deployed at:** `hacknet.tech`

---

## Core Features

### User Experience
- **Authentication & Registration** — Email/password with magic-link verification, plus OAuth integration (Yandex, GitHub, Telegram)
- **User Profiles** — Onboarding flow, questionnaire, avatar, bio, locale/timezone settings
- **Home Dashboard** — Personal progress overview
- **Education Catalog** — Structured learning paths with courses, modules, and lessons
- **Task Pages** — Individual CTF challenges with descriptions, hints, and flag submission
- **Championship & Ratings** — Competitive leaderboards (contest rating, practice rating, first blood)
- **Knowledge Base** — CVE-related articles and vulnerability documentation
- **Feedback System** — User support and admin area

### Challenge Types

| Type | Description | Access Type |
|------|-------------|-------------|
| **Forensics** | Image metadata analysis, EXIF steganography, hidden data in photos | `file` |
| **Cryptography** | Cipher encryption/decryption challenges (Caesar, Vigenère, XOR, Base64 chains) | `just_flag` |
| **Web (XSS)** | Cross-site scripting challenges with DOM manipulation, CSP bypass | `link` |
| **Chat (LLM)** | AI-powered interactive challenges, prompt injection, jailbreak detection | `chat` |

---

## Tech Stack

### Backend (`/backend`)

| Technology | Purpose |
|------------|---------|
| **Python 3.11 + FastAPI** | Async REST API |
| **PostgreSQL** | Primary database (port 6432 via PgBouncer) |
| **SQLAlchemy 2.0** | Async ORM with `asyncpg` driver |
| **pgvector** | Semantic search via cosine similarity (256-dim embeddings) |
| **JWT Auth** | 15-min access tokens + 48-hour rotating refresh tokens |
| **Yandex Cloud Object Storage** | S3-compatible file storage for challenge artifacts |
| **Yandex Cloud LLM (YandexGPT)** | AI-powered challenge generation via OpenAI SDK |
| **Pillow, piexif, pycryptodome** | Image processing and cryptography utilities |

### Frontend (`/frontend`)

| Technology | Purpose |
|------------|---------|
| **React 19** | UI framework (bootstrapped with CRA) |
| **React Router DOM v7** | Hash-based routing (for S3 static hosting) |
| **Axios** | HTTP client with response caching and token refresh |
| **Tailwind CSS v4** | Utility-first styling |

---

## Architecture

### Backend Structure
```
backend/
├── app/
│   ├── main.py              # FastAPI app, CORS, middleware, router registration
│   ├── config.py            # Pydantic settings (.env configuration)
│   ├── database.py          # Async SQLAlchemy engine + session factory
│   ├── routes/              # HTTP endpoints
│   │   ├── auth.py          # Authentication (login, register, OAuth callbacks)
│   │   ├── profile.py       # User profile management
│   │   ├── education.py     # Courses, lessons, modules
│   │   ├── contests.py      # Championship, submissions
│   │   ├── ratings.py       # Leaderboards
│   │   ├── feedback.py      # User feedback
│   │   ├── knowledge.py     # KB articles, CVE sync
│   │   └── ai_generate.py   # AI challenge generation (GRPO pipeline)
│   ├── services/            # Business logic
│   │   ├── task_generation.py
│   │   ├── article_generation.py
│   │   ├── chat_task.py
│   │   ├── nvd_sync.py      # NVD CVE database sync
│   │   ├── storage.py       # Yandex S3 integration
│   │   ├── prompt_loader.py # Database-stored LLM prompts
│   │   └── ai_generator/    # GRPO-based challenge generation
│   │       ├── pipeline.py       # Main orchestrator
│   │       ├── reward.py         # Rule-based + LLM reward scoring
│   │       ├── reviewer.py       # LLM-as-judge quality assessment
│   │       ├── embedding_service.py  # Yandex embeddings API
│   │       ├── rag_context.py    # pgvector semantic search
│   │       ├── crypto_utils.py   # Cipher functions
│   │       ├── forensics_utils.py # Image metadata injection
│   │       ├── xss_templates.py  # XSS page templates
│   │       └── chat_utils.py     # LLM prompt engineering
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── auth/                # JWT and auth dependencies
│   └── security/            # Rate limiting
├── migrations/              # SQL migration scripts
├── tests/                   # Test suite
└── requirements.txt
```

### Frontend Structure
```
frontend/
├── src/
│   ├── App.js               # Router with protected routes
│   ├── pages/
│   │   ├── Home.jsx
│   │   ├── Login.jsx
│   │   ├── Register.jsx     # Multi-step registration flow
│   │   ├── AuthBridge.jsx   # OAuth continuation
│   │   ├── Profile.jsx
│   │   ├── Championship.jsx
│   │   ├── Education.jsx
│   │   ├── Knowledge.jsx
│   │   ├── Rating.jsx
│   │   ├── Admin.jsx
│   │   └── AIGenerator/     # AI challenge generation UI (admin/PRO)
│   ├── components/
│   │   ├── Layout/
│   │   ├── Header/
│   │   ├── Sidebar/
│   │   ├── modals/
│   │   ├── icons/
│   │   └── AuthUI.jsx
│   └── services/
│       └── api.js           # Axios instance with caching, token management
├── package.json
└── README.md
```

### Database Schema (`/schema.sql`)

**Key Tables:**
- `users`, `user_profiles`, `user_ratings` — Authentication and user data
- `user_auth_identities` — OAuth provider bindings (Yandex, GitHub, Telegram)
- `auth_refresh_tokens` — Rotating refresh token sessions (48h inactivity window)
- `auth_registration_flows` — Draft registration state for magic-link/OAuth continuation
- `tariff_plans`, `user_tariffs` — FREE/PRO/CORP subscriptions (first 1000 get promo via trigger)
- `tasks`, `task_flags`, `task_materials` — CTF challenges
- `task_chat_sessions`, `task_chat_messages` — LLM interactive challenges
- `contests`, `contest_tasks`, `contest_participants`, `submissions` — Competitive mode
- `kb_entries`, `kb_comments`, `nvd_sync_log` — CVE knowledge base with pgvector embeddings
- `courses`, `course_modules`, `lessons`, `lesson_tasks` — Educational content
- `ai_generation_batches`, `ai_generation_variants` — GRPO challenge generation audit log
- `ai_base_images`, `ai_xss_templates` — Base assets for AI generation
- `llm_generations`, `prompt_templates` — LLM audit log and prompt management

---

## AI Challenge Generation (GRPO Pipeline)

The platform features an **AI-powered CTF challenge generator** using a GRPO-inspired pipeline (adapted from DeepSeek-R1, arXiv:2501.12948):

### Pipeline Flow
1. **Semantic RAG** — Embed generation query via Yandex text-search API, pull relevant CVEs from `kb_entries` via pgvector cosine similarity
2. **Generate N Variants** — Parallel LLM calls with different temperatures (e.g., 0.7, 0.8, 0.9, 1.0, 1.1)
3. **Create Artifacts** — Deterministic artifact generation from specs (images, encrypted text, HTML pages, chat prompts)
4. **Reward Scoring** — Binary rule-based checks (FUNCTIONAL, SOLVABILITY, NON_TRIVIALITY, FORMAT) + LLM-as-judge quality assessment
5. **Group-Relative Advantage** — Compute Â_i = (r_i - mean) / std for each variant
6. **Rejection Gate** — Filter to variants passing all binary checks
7. **Selection** — Pick variant with highest advantage among passed
8. **Store ALL Results** — Both winners and losers stored with failure reasons for feedback loop
9. **Publish** — Create `tasks`, `task_flags`, `task_materials` entries from selected variant

### Reward Types
| Type | Description |
|------|-------------|
| **FUNCTIONAL** | Artifact created without errors |
| **SOLVABILITY** | Flag can be recovered using the writeup |
| **NON_TRIVIALITY** | Flag not trivially exposed (not in plaintext, not in filename) |
| **FORMAT** | Spec has all required fields (title, description, flag, writeup, hints) |
| **QUALITY** | LLM-as-judge scores: educational_value, scenario_realism, hint_quality, writeup_clarity, difficulty_calibration |

---

## Authentication Flow

### Session Semantics
- **Access tokens:** 15-minute TTL (stored in localStorage)
- **Refresh tokens:** 48-hour inactivity window (HttpOnly cookie, rotating on use)
- **Real session policy:** Users stay logged in as long as they refresh within 48 hours
- **Logout trigger:** Only when refresh fails with `401` (expired/revoked)

### OAuth Providers
| Provider | Scopes | Notes |
|----------|--------|-------|
| **Yandex** | `login:email`, `login:info`, `login:avatar` | Auto-link if email exists in DB |
| **GitHub** | `user:email`, `read:user` | Auto-link if email exists in DB |
| **Telegram** | OIDC `id_token` via JWKS | Requires email attachment post-login (Telegram doesn't return email) |

**Disabled placeholders:** Apple, Google (UI present but inactive)

### Auth Endpoints
```
POST   /api/auth/registration/email/start
POST   /api/auth/registration/email/resend
GET    /api/auth/registration/email/callback
GET    /api/auth/registration/flow
POST   /api/auth/registration/complete

GET    /api/auth/yandex/start
GET    /api/auth/yandex/callback

GET    /api/auth/github/start
GET    /api/auth/github/callback

GET    /api/auth/telegram/start      # PKCE flow → oauth.telegram.org
GET    /api/auth/telegram/callback   # JWKS validation at oauth.telegram.org/.well-known/jwks.json
POST   /api/auth/registration/email/attach  # Telegram users add email
```

---

## Environment Variables

### Backend (`.env`)
```ini
# Core
SECRET_KEY=...
DB_HOST=...
DB_PORT=6432
DB_NAME=hacknet
DB_USER=...
DB_PASSWORD=...

# JWT Auth
REFRESH_TOKEN_COOKIE_NAME=refresh_token
REFRESH_TOKEN_COOKIE_SECURE=true
REFRESH_TOKEN_COOKIE_SAMESITE=lax
REFRESH_TOKEN_EXPIRY_HOURS=48

# Yandex OAuth
YANDEX_CLIENT_ID=...
YANDEX_CLIENT_SECRET=...
YANDEX_OAUTH_SCOPES=login:email,login:info,login:avatar

# GitHub OAuth
GITHUB_CLIENT_ID=...
GITHUB_CLIENT_SECRET=...
GITHUB_OAUTH_SCOPES=user:email,read:user

# Telegram OIDC
TELEGRAM_CLIENT_ID=...       # From BotFather → Web Login
TELEGRAM_CLIENT_SECRET=...   # From BotFather → Web Login

# Email Verification
YANDEX_MAIL_LOGIN=...
YANDEX_MAIL_PASSWORD=...
SMTP_HOST=smtp.yandex.ru
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_FROM=noreply@hacknet.tech
MAGIC_LINK_TTL_HOURS=24

# Yandex Cloud S3
S3_ENDPOINT=https://storage.yandexcloud.net
S3_ACCESS_KEY=...
S3_SECRET_KEY=...
S3_BUCKET=...

# Yandex Cloud LLM
YANDEX_CLOUD_API_KEY=...
YANDEX_CLOUD_FOLDER=...

# AI Generator
AI_GEN_MODEL=yandexgpt
AI_GEN_NUM_VARIANTS=5
AI_GEN_MAX_RETRIES=2
AI_GEN_MIN_REWARD_THRESHOLD=0.6
AI_GEN_BASE_TEMPERATURE=0.7
AI_GEN_TEMPERATURE_STEP=0.1
AI_GEN_RAG_CONTEXT_LIMIT=5
```

### Frontend
```ini
REACT_APP_API_BASE_URL=https://api.hacknet.tech   # Production
REACT_APP_API_BASE_URL=http://localhost:8000      # Development
```

---

## Local Development

### Backend
```bash
cd backend
pip install -r requirements.txt

# Run development server
python -m uvicorn app.main:app --reload --port 8000

# Run tests
python -m unittest discover -s tests -p "test_*.py"

# Run DB maintenance
python -m app.scripts.db_maintenance

# Backfill embeddings for kb_entries
python -m app.scripts.backfill_embeddings
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
REACT_APP_API_BASE_URL=https://api.hacknet.tech npm run build
```

### API Documentation
Backend exposes OpenAPI docs at: `http://localhost:8000/docs`

---

## Production Deployment

### Infrastructure
- **Frontend:** Static build hosted on Yandex Cloud Object Storage (S3) with CloudFront CDN
- **Backend:** FastAPI on Yandex Cloud Serverless Containers (auto-scaling)
- **Database:** PostgreSQL with PgBouncer connection pooling (port 6432)
- **Domain:** `hacknet.tech`

### CI/CD (GitHub Actions)
- **CI Pipeline:** Backend tests + Docker build validation, Frontend tests + build
- **CD Pipeline:** Triggered on `v*` tags or manual dispatch
  - Build and push backend Docker image to Yandex Container Registry
  - Deploy to Serverless Containers with environment variables
  - Build frontend and sync to S3 with cache-control headers

### OAuth Callback URLs (Production)
```
https://api.hacknet.tech/api/auth/yandex/callback
https://api.hacknet.tech/api/auth/github/callback
https://api.hacknet.tech/api/auth/telegram/callback
```

### Startup DB Maintenance
- DB compatibility logic in `backend/app/database.py`
- No Alembic migrations used; manual SQL migrations in `backend/migrations/`
- `RUN_STARTUP_DB_MAINTENANCE=false` by default

---

## Key Conventions

| Convention | Value |
|------------|-------|
| DB port | 6432 (PgBouncer) |
| Timestamps | `TIMESTAMPTZ` (UTC with timezone) |
| Slow request threshold | 1000ms (logged via `X-Process-Time-Ms` header) |
| Frontend routing | HashRouter (for S3 static hosting) |
| Access token TTL | 15 minutes |
| Refresh token window | 48 hours of inactivity |
| AI generation variants | 5 (configurable 3-7) |
| Embedding dimension | 256 (Yandex text-search model) |

---

## Recent Changes (RAG Improvement Sprint)

### Problem Fixed
The AI generator was producing nearly identical scenarios that just mentioned CVE IDs (e.g., "CVE-1111111 message") without creating unique, CVE-inspired challenge scenarios.

### Root Causes Identified
1. **Poor RAG context format** — Only showed raw CVE ID + description, no scenario guidance
2. **Generic query templates** — Semantic search found irrelevant CVEs
3. **Missing translation** — CVE descriptions were in English, but generator worked in Russian
4. **Weak prompt instructions** — No explicit requirement to use CVE as scenario inspiration
5. **Inefficient RAG grounding check** — Re-embedded entries instead of using pre-computed vectors

### Changes Made

#### 1. Enhanced RAG Context (`rag_context.py`)
- **Expanded query templates** with domain keywords (authentication, session, DOM, cookie, etc.)
- **Added scenario templates** (`_SCENARIO_TEMPLATES`) for each task type:
  - `crypto_text_web`: 4 scenarios (intercepted message, weak tokens, protocol attack, backdoor)
  - `forensics_image_metadata`: 4 scenarios (crime scene photo, digital forensics, data leak)
  - `web_static_xss`: 4 scenarios (reflected/stored/DOM-based XSS)
  - `chat_llm`: 4 scenarios (prompt injection, jailbreak, extraction)
- **Improved `to_prompt_section()`** with explicit instructions: "НЕ дублируй CVE — создай уникальный сценарий"

#### 2. CVE Translation Service (`translation_service.py`)
- **New service** using `deepseek-v32` model for high-quality full translation
- **Translates** `ru_title` + `ru_summary` + `ru_explainer` (full CVE content)
- **Integrated into NVD sync** — new CVEs are fully translated automatically
- **Backfill script** (`scripts/translate_kb_entries.py`) for existing entries:
  ```bash
  cd backend
  python -m app.scripts.translate_kb_entries --limit 5     # Test run (5 CVEs)
  python -m app.scripts.translate_kb_entries               # Full backfill
  ```
- **Cost:** ~2 RUB per CVE (full translation) → ~7700 RUB for 3863 entries (one-time)

#### 3. Updated Generator Prompts
- **`crypto_generator.txt`**: Added explicit requirements to use CVE from RAG, create unique scenarios
- **`forensics_generator.txt`**: Same improvements with scenario examples

#### 4. Optimized RAG Grounding Check (`validator.py`)
- **Uses pre-computed embeddings** from `kb_entries.embedding` column
- **Added `stored_embedding` field** to `CVEEntry` dataclass
- **Adjusted similarity thresholds** (0.7/0.5/0.3) for scenario-to-CVE comparison

#### 5. Admin Dashboard Translation Status
- **Updated `AdminNvdSync` schema** with `translation_total/completed/failed` fields
- **SQL migration** (`migrations/add_translation_tracking_to_nvd_sync_log.sql`)
- **Progress tracking** visible in admin panel alongside embedding status

### Files Modified/Created
| File | Change |
|------|--------|
| `backend/app/services/ai_generator/rag_context.py` | Enhanced queries + scenario templates |
| `backend/app/services/ai_generator/translation_service.py` | NEW — yandexgpt-lite translation |
| `backend/app/services/ai_generator/validator.py` | Optimized RAG grounding check |
| `backend/app/services/nvd_sync.py` | Added translation hook + tracking |
| `backend/app/scripts/translate_kb_entries.py` | NEW — backfill script |
| `backend/app/prompts/crypto_generator.txt` | Stronger RAG requirements |
| `backend/app/prompts/forensics_generator.txt` | Stronger RAG requirements |
| `backend/app/schemas/admin.py` | Translation status fields |
| `backend/migrations/add_translation_tracking_to_nvd_sync_log.sql` | NEW — DB migration |

### Expected Results
- **Unique scenarios** inspired by CVE rather than copying CVE descriptions
- **Russian-language CVE context** for better LLM understanding
- **4 distinct scenario templates** per task type for variety
- **Cost-effective translation** at ~0.2 RUB/1K tokens (yandexgpt-lite)

---

## Recent Changes (Admin Panel Reorganization — March 2026)

### Problem Fixed
The admin panel was a single **3,134-line `Admin.jsx` file** with 4 large modals (Knowledge Base, Tasks, Contests, Prompts) mixed with dashboard logic, making it difficult to maintain, extend, or debug.

### Goals
1. **Improve code organization** — Split monolithic file into modular components
2. **Better UX** — Replace modals with slide-in drawer panels
3. **Cleaner dashboard** — Card-based layout with clear visual hierarchy
4. **Reusability** — Extract common components (StatCard, SectionCard, Drawer, etc.)
5. **Maintain design consistency** — Follow existing Figma design system

### Architecture Changes

#### New File Structure
```
frontend/src/pages/Admin/
├── index.jsx                    # Main admin page (~290 lines, orchestration only)
├── Dashboard/
│   ├── FeedbackPanel.jsx        # Latest feedback section with resolve action
│   ├── ChampionshipWidget.jsx   # Current championship status card
│   └── RecentArticleCard.jsx    # Last KB article preview
├── Drawers/
│   ├── KnowledgeBaseDrawer.jsx  # KB article CRUD (960px wide, 2-column layout)
│   ├── TaskManagerDrawer.jsx    # Task CRUD + AI generation (960px wide)
│   ├── ContestPlannerDrawer.jsx # Contest creation (640px wide)
│   └── PromptManagerDrawer.jsx  # LLM prompt template editor (640px wide)
├── Widgets/
│   ├── Drawer.jsx               # Base drawer component with overlay & ESC key
│   ├── StatCard.jsx             # Reusable statistics card
│   ├── SectionCard.jsx          # Reusable section container
│   ├── NvdSyncWidget.jsx        # NVD sync progress with real-time polling
│   ├── FeedbackResolver.jsx     # Feedback resolution confirmation modal
│   └── Icons.jsx                # Icon set (Users, Activity, Trophy, etc.)
└── hooks/
    └── useAdminDashboard.js     # Custom hook for dashboard data fetching
```

#### Component Breakdown

| Component | Lines | Responsibility |
|-----------|-------|----------------|
| `index.jsx` | ~290 | Dashboard layout, drawer state management, NVD sync orchestration |
| `KnowledgeBaseDrawer.jsx` | ~550 | Article create/edit with AI generation |
| `TaskManagerDrawer.jsx` | ~340 | Task CRUD with AI generation |
| `ContestPlannerDrawer.jsx` | ~235 | Contest creation with task selection |
| `PromptManagerDrawer.jsx` | ~200 | Prompt template list + editor |
| `Dashboard/*.jsx` | ~80 each | Feedback, Championship, Article widgets |
| `Widgets/*.jsx` | ~50-150 each | Reusable UI components |

**Total reduction:** 3,134 lines → ~2,000 lines (modular, maintainable)

### UX Improvements

#### 1. Card-Based Dashboard Layout
```
┌─────────────────────────────────────────────────────────────┐
│  Header: Title + Action Buttons (KB, Tasks, Contests, etc.)│
├─────────────────────────────────────────────────────────────┤
│  [Stat: Users] [Stat: Active] [Stat: Paid] [Stat: Submits] │
├──────────────────────────┬──────────────────────────────────┤
│  Latest Feedback (3-5)   │  Current Championship Widget     │
│  - User + topic          │  - Title + status badge          │
│  - Message preview       │  - Dates, submissions count      │
│  - Resolve button        │  - Public/leaderboard toggles    │
├──────────────────────────┴──────────────────────────────────┤
│  NVD Sync Widget (full width)                               │
│  - Progress bar + status + last run time                    │
├─────────────────────────────────────────────────────────────┤
│  Recent Article Card (full width)                           │
│  - Title, summary, tags, CVE link                           │
└─────────────────────────────────────────────────────────────┘
```

#### 2. Drawer Panels (Slide-in from Right)
- **Width:** 640px (single column) / 960px (dual column for KB/Tasks)
- **Overlay:** Backdrop blur + dark overlay (`bg-black/70 backdrop-blur-sm`)
- **Animation:** Smooth slide-in (CSS transitions, 200ms)
- **Keyboard:** `Esc` key closes drawer, `Ctrl+S` saves (planned)
- **Header:** Title + subtitle + close button
- **Content:** Scrollable area with proper padding
- **Footer:** Sticky action buttons (Cancel/Save/Delete)

#### 3. Removed Duplicates
- **NVD Fetch button** — Now only in `NvdSyncWidget` (was duplicated in header)
- **Centralized NVD state** — Single source of truth with polling

### Technical Improvements

#### 1. Custom Hooks
```javascript
// useAdminDashboard.js
export function useAdminDashboard(navigate) {
  // Returns: { loading, dashboard, error, refresh, setDashboard }
}

export function useNvdSync(loadDashboard) {
  // Returns: { isRunning, error, handleFetch }
}
```

#### 2. Reusable Components
- **`Drawer.jsx`** — Base drawer with overlay, ESC key handling, body scroll lock
- **`StatCard.jsx`** — Standardized stats display with icon + tone
- **`SectionCard.jsx`** — Section container with title/subtitle/action slots
- **`NvdSyncWidget.jsx`** — Self-contained NVD sync status with progress bar

#### 3. State Management
- **Drawer states** — Simple `useState` for open/close
- **NVD polling** — `useEffect` with 2.5s interval when status is `fetching`/`embedding`
- **Feedback resolution** — Modal confirmation before marking as resolved

### Files Modified/Created

| File | Change |
|------|--------|
| `frontend/src/pages/Admin/index.jsx` | NEW — Main admin page (replaces old Admin.jsx) |
| `frontend/src/pages/Admin/Dashboard/*.jsx` | NEW — Dashboard widgets |
| `frontend/src/pages/Admin/Drawers/*.jsx` | NEW — Drawer panels |
| `frontend/src/pages/Admin/Widgets/*.jsx` | NEW — Reusable components |
| `frontend/src/pages/Admin/hooks/useAdminDashboard.js` | NEW — Custom hooks |
| `frontend/src/App.js` | Updated import path for Admin |
| `frontend/src/pages/Admin.jsx` | BACKED UP → `Admin.jsx.backup` |

### Build Status
✅ **Build successful** — No errors, 2 minor ESLint warnings (unused imports, can be ignored)

### Code Quality Metrics

| Metric | Before | After |
|--------|--------|-------|
| Main file lines | 3,134 | ~290 |
| Components | 1 monolith | 12 modular files |
| Modals | 4 embedded | 4 drawers + 1 resolver |
| Reusability | 0 | 6 reusable components |
| Testability | Low (tightly coupled) | High (isolated components) |

### Future Enhancements (Planned)
1. **Toast notifications** — Success-error feedback for actions
2. **Unsaved changes warning** — Prompt before closing drawer with edits
3. **Keyboard shortcuts** — `Ctrl+S` save, `Ctrl+N` new, `Ctrl+F` search
4. **Task edit drawer** — Full CRUD operations for existing tasks
5. **Contest edit drawer** — Modify ongoing contests
6. **Batch operations** — Delete multiple tasks/articles at once
7. **Analytics dashboard** — Charts for user activity, submissions, ratings

### How to Use
```bash
cd frontend
npm start
# Navigate to /admin (requires admin role)
```

### Design Consistency
All components follow the existing **Figma design system**:
- **Colors:** `#9B6BFF` (primary purple), white opacity scales
- **Typography:** `font-sans-figma`, `font-mono-figma`
- **Border radius:** `rounded-[10px]`, `rounded-[12px]`, `rounded-[18px]`
- **Spacing:** Tailwind scale (`gap-4`, `gap-6`, `p-6`, `p-8`)
- **Transitions:** `transition-colors duration-200`, `hover:border-[#9B6BFF]/60`

## Qwen Added Memories
- User prefers very short, concise summaries when documenting work

---

## Recent Changes (User Task Variants — UGC Feature — March 2026)

### Feature: "Создать похожее"
Users generate custom variants of existing tasks (Crypto/Forensics/Web only, NOT chat).

### Backend Files
| File | Purpose |
|------|---------|
| `models/user_task_variant.py` | NEW — DB models (requests, votes) |
| `services/ai_generator/user_pipeline.py` | NEW — Pipeline with LLM review (3 variants) |
| `services/ai_generator/prompt_safety.py` | NEW — Injection detection (EN/RU) |
| `routes/user_variants.py` | NEW — API endpoints + rate limiting (5/hour) |
| `migrations/create_user_task_variants.sql` | NEW — DB schema |

### Frontend Files
| File | Purpose |
|------|---------|
| `UserTaskVariants/TicTacToe/` | NEW — Unbeatable minimax bot |
| `UserTaskVariants/TaskVariantGenerator.jsx` | NEW — Dialog (3 steps) |
| `UserTaskVariants/VariantCard.jsx` | NEW — Clickable cards with votes |
| `UserTaskVariants/VariantList.jsx` | NEW — Sorted by rating |
| `EducationTask.jsx` | MODIFIED — Added variants section |

### Flow
1. User clicks "Создать похожее"
2. Enters wishes (e.g., "Полегче, но больше этапов")
3. Plays tic-tac-toe (~45-60 sec)
4. Variant auto-published as task (`task_kind='ugc'`, `state='draft'`)
5. Click card → navigate to task

### Prompts Updated
- `crypto_generator.txt`, `forensics_generator.txt`, `xss_generator.txt` — Added user_wishes handling

### Build Status
✅ Frontend builds successfully
✅ Backend runs (tested endpoints)
