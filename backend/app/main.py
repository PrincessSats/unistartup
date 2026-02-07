import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routes import auth, pages, profile, contests, ratings, feedback, knowledge

logger = logging.getLogger(__name__)

app = FastAPI(
    title="HackNet Platform API",
    description="API для платформы по кибербезопасности",
    version="1.0.0"
)

allow_credentials = settings.CORS_ALLOW_CREDENTIALS
if allow_credentials and "*" in settings.CORS_ALLOW_ORIGINS:
    logger.warning(
        "Unsafe CORS config detected: wildcard origin with credentials. "
        "Forcing allow_credentials=False."
    )
    allow_credentials = False

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ALLOW_ORIGINS,
    allow_origin_regex=settings.CORS_ALLOW_ORIGIN_REGEX,
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
