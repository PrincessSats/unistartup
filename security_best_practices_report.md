# Security Best Practices Report
Date: 2026-02-07  
Repository: `/Users/mmms/Developer/unistartup`  
Scope: Backend (`FastAPI`), Frontend (`React`), CI (`GitHub Actions`), Dockerfile, dependency posture

## Executive Summary
Проведен полный статический security-аудит с приоритетом на exploitable/high-confidence уязвимости.

- Найдено и закрыто: 6 high-impact issues.
- Остаются открытыми: 4 issues (из них 1 high supply-chain/process risk и 3 medium hardening risks).
- Ключевой прогресс: устранены утечки через SQL-логи по умолчанию, закрыта утечка внутренних ошибок, внедрены rate-limit guards на критичных endpoint’ах, добавлен `Authorization: Bearer` transport, ужесточены CORS и приватность контестов.

## Findings

### Critical / High

#### F-001 (High) Sensitive SQL Logging Enabled by Default
- Location: `backend/app/database.py:7-10`
- Evidence (before fix): `echo=True` on SQLAlchemy engine.
- Impact: SQL statements and potentially sensitive values могут попадать в логи.
- Status: **Fixed**
- Fix: добавлен env-switch `SQL_ECHO` с безопасным default `false` (`backend/app/config.py:24`, `backend/app/database.py:9`).

#### F-002 (High) Internal Error Details Exposed to Client
- Location: `backend/app/routes/profile.py:306-311`
- Evidence (before fix): возврат типа и текста исключения в `HTTPException.detail`.
- Impact: утечка внутренней структуры и диагностики storage-layer.
- Status: **Fixed**
- Fix: серверное логирование через `logger.exception(...)` + безопасный generic message для клиента.

#### F-003 (High) Overly Permissive CORS
- Location: `backend/app/main.py:25-31`
- Evidence (before fix): `allow_origins=["*"]`, `allow_credentials=True`.
- Impact: риск неправильной cross-origin модели при credentialed requests.
- Status: **Fixed**
- Fix: CORS полностью переведен на env-конфиг (`CORS_ALLOW_*`), плюс защитный guard для wildcard+credentials (`backend/app/main.py:17-23`).

#### F-004 (High) Missing Abuse Controls on Sensitive Endpoints
- Location:
  - `backend/app/routes/auth.py:95-106` (`/auth/login`)
  - `backend/app/routes/contests.py:322-327` (`/contests/{id}/submit`)
  - `backend/app/routes/knowledge.py:312-317` (`/kb_entries/{id}/comments`)
  - `backend/app/routes/feedback.py:30-35` (`/feedback`)
- Evidence (before fix): отсутствие rate limiting.
- Impact: brute-force/spam/automation abuse.
- Status: **Fixed (phase 1)**
- Fix: внедрен in-memory limiter (`backend/app/security/rate_limit.py`) и включен на критичных endpoint’ах.

#### F-005 (High) Private Contest Access Not Strictly Enforced
- Location:
  - `backend/app/routes/contests.py:66-86`
  - `backend/app/routes/contests.py:197-199`
  - `backend/app/routes/contests.py:236-237`
  - `backend/app/routes/contests.py:332-333`
- Evidence (before fix): логика могла возвращать/разрешать private contest flows без явного deny policy.
- Impact: несанкционированный доступ к приватной активности.
- Status: **Fixed**
- Fix: явный deny для non-admin на private contest read/join/task/submit flows.

#### F-006 (High) Non-Standard Auth Header Only
- Location:
  - `backend/app/auth/dependencies.py:9-35`
  - `frontend/src/services/api.js:10-13`
  - `frontend/src/services/api.js:24-27`
- Evidence (before fix): backend принимал только `X-Auth-Token`.
- Impact: слабая интероперабельность и сложность стандартных security controls по bearer transport.
- Status: **Fixed (compat mode)**
- Fix: backend принимает `Authorization: Bearer` + legacy fallback `X-Auth-Token`; frontend отправляет оба.

### Medium

#### F-007 (Medium) In-memory Rate Limiter Is Process-Local
- Location: `backend/app/security/rate_limit.py:16-42`
- Evidence: limiter хранится в памяти процесса.
- Impact: в multi-instance deployment лимиты не глобальны.
- Status: **Open**
- Recommended Fix: вынести rate limiting на edge/Redis-based shared storage.

#### F-008 (Medium) JWT Stored in `localStorage`
- Location: `frontend/src/services/api.js:23-59`
- Evidence: `localStorage.getItem/setItem/removeItem('token')`.
- Impact: при XSS токен может быть украден.
- Status: **Open**
- Recommended Fix: migration к HttpOnly secure cookies + CSRF protection или краткоживущие memory tokens.

#### F-009 (Medium) Security-Sensitive Dependency Posture Requires Upgrade Plan
- Location: `backend/requirements.txt` (not yet changed in this phase)
- Evidence: `starlette==0.38.6` + historical advisory surface around multipart/file serving.
- Impact: потенциальная экспозиция к известным DoS/serving-class issues depending on deployed path.
- Status: **Open**
- Recommended Fix: совместимое обновление `fastapi/starlette` с regression testing.

#### F-010 (Medium) CI Supply-Chain Hardening Gaps
- Location: `.github/workflows/deploy.yml:35`, `.github/workflows/deploy.yml:18`, `.github/workflows/deploy.yml:72`
- Evidence:
  - `curl ... | bash` install path for CLI
  - GitHub actions pinned by major tags (`@v3`) instead of immutable SHAs
- Impact: повышенный supply-chain risk в CI/CD.
- Status: **Open**
- Recommended Fix: pin actions to commit SHAs, use checksum-verified install artifacts.

## Implemented Changes
- `backend/app/config.py`: `SQL_ECHO`, `CORS_ALLOW_*`, tolerant env parsing for list fields.
- `backend/app/database.py`: SQL echo controlled via env (`SQL_ECHO`), default safe.
- `backend/app/main.py`: CORS hardening + structured logging instead of `print`.
- `backend/app/auth/dependencies.py`: `Authorization: Bearer` support with legacy fallback.
- `backend/app/routes/profile.py`: sanitized 500 errors, server-side exception logging.
- `backend/app/routes/auth.py`: rate limiting for login.
- `backend/app/routes/feedback.py`: rate limiting for feedback submit.
- `backend/app/routes/knowledge.py`: rate limiting for comment creation.
- `backend/app/routes/contests.py`: privacy enforcement + submit rate limiting.
- `backend/app/security/rate_limit.py`: centralized rate limiting utility.
- `frontend/src/services/api.js`: bearer header sending (+ fallback header).
- Added tests:
  - `backend/tests/test_rate_limit.py`
  - `backend/tests/test_security_settings.py`

## Verification / Tests
- Passed:
  - `PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend/tests -p 'test_*.py'`
  - `PYTHONPATH=backend ... .venv/bin/python -c "from app.main import app; print('routes', len(app.routes))"`
  - SQL echo behavior check:
    - without `SQL_ECHO` => `False`
    - with `SQL_ECHO=true` => `True`
- Not passed in current environment:
  - `CI=true npm test -- --watchAll=false` in `/frontend` failed due module resolution (`react-router-dom`) in local test env setup.

## Next Remediation Queue
1. Upgrade and compatibility test for `fastapi/starlette` and related security-sensitive dependencies.
2. Replace process-local limiter with distributed limiter.
3. Migrate auth from `localStorage` token model to cookie/session model with CSRF-safe flow.
4. Harden CI supply-chain: pin action SHAs, replace unverified bootstrap installs.

