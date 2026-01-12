from fastapi import Depends, HTTPException, status, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.database import get_db
from app.models.user import User, UserProfile
from app.auth.security import decode_access_token

async def get_current_user(
    x_auth_token: Optional[str] = Header(None),  # Читаем X-Auth-Token
    db: AsyncSession = Depends(get_db)
) -> tuple[User, UserProfile]:
    """
    Получает текущего авторизованного пользователя.
    Читает токен из заголовка X-Auth-Token
    """
    
    if not x_auth_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен не предоставлен"
        )
    
    # Расшифровываем токен
    payload = decode_access_token(x_auth_token)
    
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
    """
    user, profile = current_user_data
    
    if profile.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ запрещен. Требуются права администратора."
        )
    
    return user, profile