from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, pages, profile

print("✅ Роутеры загружены: auth, pages, profile")  # ← добавь это
app = FastAPI(
    title="HackNet Platform API",
    description="API для платформы по кибербезопасности",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(pages.router)
app.include_router(profile.router)  # ← новый роутер

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