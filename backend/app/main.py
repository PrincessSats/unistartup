import logging
import re

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import auth, pages, profile, contests, ratings, feedback, knowledge
from app.database import ensure_auth_schema_compatibility

logger = logging.getLogger(__name__)

app = FastAPI(
    title="HackNet Platform API",
    description="API для платформы по кибербезопасности",
    version="1.0.0"
)

allow_origins = settings.cors_allow_origins
allow_credentials = settings.CORS_ALLOW_CREDENTIALS
if allow_credentials and "*" in allow_origins:
    logger.warning(
        "Unsafe CORS config detected: wildcard origin with credentials. "
        "Forcing allow_credentials=False."
    )
    allow_credentials = False

allow_origin_regex = settings.CORS_ALLOW_ORIGIN_REGEX
if allow_origin_regex:
    try:
        re.compile(allow_origin_regex)
    except re.error:
        logger.exception("Invalid CORS_ALLOW_ORIGIN_REGEX=%r. Ignoring it.", allow_origin_regex)
        allow_origin_regex = None

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

logger.info("Routers loaded: auth, pages, profile, contests, ratings, feedback, knowledge")

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
    await ensure_auth_schema_compatibility()
