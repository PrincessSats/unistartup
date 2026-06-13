# HackNet Platform — Project Documentation (GEMINI.md)
Always use jCodemunch-MCP tools — never fall back to Read, Grep, Glob, or Bash for code exploration.
- Before reading a file: use get_file_outline or get_file_content
- Before searching: use search_symbols or search_text
- Before exploring structure: use get_file_tree or get_repo_outline
- Call list_repos first; if the project is not indexed, call index_folder with the current directory.
## 🎯 Project Overview
**HackNet** is a comprehensive cybersecurity CTF (Capture The Flag) learning platform designed for hands-on security education. It features automated challenge generation, structured learning paths, and competitive leaderboards.

- **URL:** `hacknet.tech`
- **Core Goal:** Teach practical cybersecurity skills through realistic, hands-on challenges.

---

## 🏗 Architecture & Tech Stack

### Backend (`/backend`)
- **Framework:** Python 3.11 + FastAPI (Async REST API)
- **Database:** PostgreSQL (with `pgvector` for semantic search)
- **ORM:** SQLAlchemy 2.0 (Async)
- **Auth:** JWT (15m Access / 48h Refresh Tokens) + OAuth (Yandex, GitHub, Telegram)
- **Storage:** Yandex Cloud Object Storage (S3-compatible)
- **AI:** Yandex Cloud LLM (YandexGPT) via OpenAI SDK
- **Utilities:** Pillow (Images), piexif (Metadata), pycryptodome (Crypto)

### Frontend (`/frontend`)
- **Framework:** React 19 (CRA)
- **Routing:** React Router DOM v7 (Hash-based for S3 hosting)
- **Styling:** Tailwind CSS v4
- **API Client:** Axios (with interceptors for token refresh)

---

## 🚀 Key Features

### 1. AI Challenge Generation (GRPO Pipeline)
A sophisticated pipeline inspired by DeepSeek-R1 (GRPO) for generating high-quality CTF tasks:
- **Semantic RAG:** Uses `pgvector` to find relevant CVEs from a Knowledge Base.
- **Multi-Variant Generation:** Generates N variants in parallel with varying temperatures.
- **Reward Scoring:** 
    - **Binary Checks:** Functional correctness, solvability, non-triviality, format.
    - **Soft Checks:** RAG grounding (semantic similarity).
    - **LLM-as-Judge:** Quality assessment (educational value, realism, etc.).
- **Advantage Selection:** Picks the best variant based on group-relative advantage.

### 2. Challenge Types
- **Forensics:** Image metadata, EXIF steganography.
- **Cryptography:** Cipher chains (Caesar, Vigenère, XOR, Base64).
- **Web (XSS):** Reflected, DOM-based, and bypass challenges.
- **Chat (LLM):** Prompt injection and jailbreaking interactive tasks.

### 3. Education & Community
- **Education Catalog:** Structured courses, modules, and lessons.
- **Knowledge Base:** CVE documentation with semantic search.
- **Ratings:** Global leaderboards for Contests, Practice, and "First Bloods".

---

## 🛠 Development Workflow

### Commands
- **Backend:** `uvicorn app.main:app --host 0.0.0.0 --port 8080`
- **Frontend:** `npm start`
- **DB Maintenance:** `python -m app.scripts.db_maintenance`
- **Embedding Backfill:** `python -m app.scripts.backfill_embeddings`

### Environment Config
Managed via `.env` files in root or `backend/`. Key variables include:
- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
- `SECRET_KEY`, `ALGORITHM`
- `YANDEX_CLOUD_API_KEY`, `YANDEX_CLOUD_FOLDER`
- `S3_BUCKET_NAME`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`

### Deployment
- **Backend:** Dockerized (see `backend/Dockerfile`).
- **Frontend:** Static build deployed to S3/CDN.
- **CI/CD:** GitHub Actions (see `.github/workflows/`).

---

## 📂 Directory Structure

### Root
- `backend/`: FastAPI application code.
- `frontend/`: React application code.
- `design/`: UI/UX assets, snapshots, and style definitions.
- `migrations/`: SQL scripts for database schema updates.
- `schema.sql`: Complete database schema definition.

### Backend Detail (`backend/app/`)
- `routes/`: API endpoint definitions.
- `models/`: SQLAlchemy ORM models.
- `services/`: Business logic (AI generation, RAG, S3, etc.).
- `schemas/`: Pydantic request/response models.

---

## 🛡 Security Standards
- **Secrets:** Never commit `.env` files. Use environment variables.
- **Auth:** Always use `get_current_user` or `get_current_admin` dependencies for protected routes.
- **CORS:** Configured via `CORS_ALLOW_ORIGIN_REGEX` in `Settings`.
