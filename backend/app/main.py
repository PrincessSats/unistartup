from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, pages

# Создаем приложение FastAPI
app = FastAPI(
    title="HackNet Platform API",
    description="API для платформы по кибербезопасности",
    version="1.0.0"
)

# Настройка CORS (чтобы frontend мог обращаться к backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # В продакшене указать конкретные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роуты
app.include_router(auth.router)
app.include_router(pages.router)

# Корневой endpoint (проверка, что сервер работает)
@app.get("/")
async def root():
    """
    Главная страница API.
    Показывает, что сервер запущен.
    """
    return {
        "message": "HackNet Platform API",
        "status": "running",
        "docs": "/docs"  # Автоматическая документация FastAPI
    }

# Эндпоинт для проверки здоровья сервера
@app.get("/health")
async def health_check():
    """
    Проверка работоспособности сервера.
    """
    return {"status": "ok"}