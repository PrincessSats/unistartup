import logging
import re
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, settings
from app.routes import auth, pages, profile, contests, ratings, feedback, knowledge, education
from app.database import ensure_auth_schema_compatibility, ensure_performance_indexes

logger = logging.getLogger(__name__)

app = FastAPI(
    title="HackNet Platform API",
    description="API для платформы по кибербезопасности",
    version="1.0.0"
)

allow_origin_regex = settings.CORS_ALLOW_ORIGIN_REGEX
if allow_origin_regex:
    try:
        re.compile(allow_origin_regex)
    except re.error:
        logger.exception("Invalid CORS_ALLOW_ORIGIN_REGEX=%r. Ignoring it.", allow_origin_regex)
        allow_origin_regex = None

allow_origins = [
    origin
    for origin in dict.fromkeys(settings.cors_allow_origins)
    if str(origin).strip()
]
allow_credentials = settings.CORS_ALLOW_CREDENTIALS
required_public_origins = [
    "https://hacknet.tech",
    "https://www.hacknet.tech",
]
for required_origin in required_public_origins:
    if required_origin not in allow_origins:
        allow_origins.append(required_origin)

if not allow_credentials and settings.REFRESH_TOKEN_COOKIE_SAMESITE == "none":
    logger.warning(
        "Refresh cookie flow requires credentials for cross-origin requests. "
        "Forcing CORS allow_credentials=True because REFRESH_TOKEN_COOKIE_SAMESITE=none."
    )
    allow_credentials = True

if allow_credentials and "*" in allow_origins:
    allow_origins = [origin for origin in allow_origins if origin != "*"]
    if not allow_origins:
        default_origins = Settings._parse_list(
            Settings.model_fields["CORS_ALLOW_ORIGINS"].default or ""
        )
        allow_origins = [
            origin
            for origin in dict.fromkeys(default_origins)
            if str(origin).strip() and origin != "*"
        ]
    logger.warning(
        "CORS wildcard origin is incompatible with credentials. "
        "Removed '*' and kept credentials enabled. Effective origins: %s",
        ", ".join(allow_origins) if allow_origins else "<none>",
    )

if allow_credentials and not allow_origins and not allow_origin_regex:
    logger.warning(
        "CORS credentials requested but no origins configured. "
        "Disabling credentials header to avoid invalid CORS responses."
    )
    allow_credentials = False

logger.info(
    "Effective CORS config: credentials=%s, origins=%s, origin_regex=%s",
    allow_credentials,
    allow_origins,
    allow_origin_regex,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_origin_regex=allow_origin_regex,
    allow_credentials=allow_credentials,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(profile.router)  # ← новый роутер
app.include_router(contests.router)
app.include_router(ratings.router)
app.include_router(feedback.router)
app.include_router(knowledge.router)
app.include_router(education.router)

logger.info("Routers loaded: auth, pages, profile, contests, ratings, feedback, knowledge, education")


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    started_at = perf_counter()
    response = await call_next(request)
    elapsed_ms = (perf_counter() - started_at) * 1000.0
    response.headers["X-Process-Time-Ms"] = f"{elapsed_ms:.2f}"
    if (
        settings.LOG_SLOW_REQUESTS
        and elapsed_ms >= settings.SLOW_REQUEST_THRESHOLD_MS
    ):
        logger.warning(
            "Slow request: %s %s status=%s time_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
        )
    return response

@app.get("/")
async def root():
    return {
        "message": "HackNet Platform API",
        "status": "running",
        "docs": "/docs"
    }

@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.on_event("startup")
async def startup_tasks():
    if not settings.RUN_STARTUP_DB_MAINTENANCE:
        logger.info(
            "Startup DB maintenance disabled by RUN_STARTUP_DB_MAINTENANCE=false "
            "(run `python -m app.scripts.db_maintenance` during deploy)."
        )
        return

    await ensure_auth_schema_compatibility()
    # На старте дополнительно гарантируем индексы для быстрых пользовательских сценариев.
    await ensure_performance_indexes()
