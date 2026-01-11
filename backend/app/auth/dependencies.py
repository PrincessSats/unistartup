from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User, UserProfile
from app.auth.security import decode_access_token

# Настройка для получения токена из заголовка Authorization
security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> tuple[User, UserProfile]:
    """
    Получает текущего авторизованного пользователя.
    
    Что делаем:
    1. Берем токен из заголовка Authorization: Bearer <token>
    2. Расшифровываем токен
    3. Находим пользователя в БД
    4. Возвращаем User и UserProfile
    
    Если токен невалидный - ошибка 401
    """
    
    # Расшифровываем токен
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен"
        )
    
    # Получаем email из токена
    email: str = payload.get("sub")
    if email is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Невалидный токен"
        )
    
    # Ищем пользователя в БД
    result = await db.execute(
        select(User, UserProfile)
        .join(UserProfile, User.id == UserProfile.user_id)
        .where(User.email == email)
    )
    user_data = result.first()
    
    if user_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден"
        )
    
    user, profile = user_data
    
    # Проверяем, активен ли аккаунт
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован"
        )
    
    return user, profile

async def get_current_admin(
    current_user_data: tuple = Depends(get_current_user)
) -> tuple[User, UserProfile]:
    """
    Проверяет, что текущий пользователь - администратор.
    Используется для защиты админских endpoints.
    """
    user, profile = current_user_data
    
    if profile.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен. Требуются права администратора."
        )
    
    return user, profile
