from fastapi import APIRouter, Depends
from app.auth.dependencies import get_current_user, get_current_admin
from app.models.user import User, UserProfile

router = APIRouter(tags=["Тестовые страницы"])

@router.get("/welcome")
async def welcome_page(
    current_user_data: tuple = Depends(get_current_user)
):
    """
    Приветственная страница для авторизованных пользователей.
    Доступна всем (и admin, и participant).
    """
    user, profile = current_user_data
    
    return {
        "message": "Молодец, БД работает, добро пожаловать!",
        "user": {
            "username": profile.username,
            "email": user.email,
            "role": profile.role
        }
    }

@router.get("/admin")
async def admin_panel(
    current_user_data: tuple = Depends(get_current_admin)
):
    """
    Админка.
    Доступна только пользователям с ролью 'admin'.
    """
    user, profile = current_user_data
    
    return {
        "message": "Добро пожаловать в админку!",
        "admin": {
            "username": profile.username,
            "email": user.email,
            "role": profile.role
        },
        "features": [
            "Управление пользователями",
            "Создание задач",
            "Управление соревнованиями"
        ]
    }