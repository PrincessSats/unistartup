"""
API для работы с профилем пользователя.

Эндпоинты:
- GET /profile - получить свой профиль
- PUT /profile - обновить username
- PUT /profile/email - сменить email  
- PUT /profile/password - сменить пароль
- POST /profile/avatar - загрузить аватарку
"""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Optional

from app.database import get_db
from app.models.user import User, UserProfile
from app.auth.security import hash_password, verify_password
from app.auth.dependencies import get_current_user
from app.services.storage import upload_avatar, delete_avatar

router = APIRouter(prefix="/profile", tags=["Профиль"])


# ========== Схемы (Pydantic модели) ==========

class ProfileResponse(BaseModel):
    """Ответ с данными профиля"""
    id: int
    email: str
    username: str
    role: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    
    class Config:
        from_attributes = True


class UpdateUsernameRequest(BaseModel):
    """Запрос на смену username"""
    username: str


class UpdateEmailRequest(BaseModel):
    """Запрос на смену email"""
    new_email: EmailStr


class UpdatePasswordRequest(BaseModel):
    """Запрос на смену пароля"""
    current_password: str
    new_password: str


class MessageResponse(BaseModel):
    """Простой ответ с сообщением"""
    message: str


# ========== Эндпоинты ==========

@router.get("", response_model=ProfileResponse)
async def get_profile(
    current_user_data: tuple = Depends(get_current_user)
):
    """
    Получить свой профиль.
    Требует авторизации (X-Auth-Token в заголовке).
    """
    user, profile = current_user_data
    
    return ProfileResponse(
        id=user.id,
        email=user.email,
        username=profile.username,
        role=profile.role,
        bio=profile.bio,
        avatar_url=profile.avatar_url
    )


@router.put("", response_model=ProfileResponse)
async def update_profile(
    data: UpdateUsernameRequest,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить username.
    Проверяем что новый username не занят другим пользователем.
    """
    user, profile = current_user_data
    
    # Проверяем что username не занят
    result = await db.execute(
        select(UserProfile).where(
            UserProfile.username == data.username,
            UserProfile.user_id != user.id  # Исключаем себя
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот username уже занят"
        )
    
    # Обновляем профиль
    profile.username = data.username
    await db.commit()
    await db.refresh(profile)
    
    return ProfileResponse(
        id=user.id,
        email=user.email,
        username=profile.username,
        role=profile.role,
        bio=profile.bio,
        avatar_url=profile.avatar_url
    )


@router.put("/email", response_model=MessageResponse)
async def update_email(
    data: UpdateEmailRequest,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Сменить email.
    Проверяем что новый email не занят.
    """
    user, profile = current_user_data
    
    # Проверяем что email не занят
    result = await db.execute(
        select(User).where(
            User.email == data.new_email,
            User.id != user.id
        )
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Этот email уже зарегистрирован"
        )
    
    # Обновляем email
    user.email = data.new_email
    await db.commit()
    
    return MessageResponse(message="Email успешно изменён")


@router.put("/password", response_model=MessageResponse)
async def update_password(
    data: UpdatePasswordRequest,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Сменить пароль.
    Требуем текущий пароль для безопасности.
    """
    user, profile = current_user_data
    
    # Проверяем текущий пароль
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный текущий пароль"
        )
    
    # Проверяем длину нового пароля
    if len(data.new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Пароль должен быть минимум 8 символов"
        )
    
    # Обновляем пароль
    user.password_hash = hash_password(data.new_password)
    await db.commit()
    
    return MessageResponse(message="Пароль успешно изменён")


@router.post("/avatar", response_model=ProfileResponse)
async def upload_user_avatar(
    file: UploadFile = File(...),
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Загрузить аватарку.
    
    Что делаем:
    1. Проверяем тип файла (только картинки)
    2. Читаем файл
    3. Загружаем в Object Storage (там сжимается)
    4. Удаляем старую аватарку
    5. Сохраняем новый URL в профиле
    """
    user, profile = current_user_data
    
    # Проверяем тип файла
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Можно загружать только изображения"
        )
    
    # Читаем файл
    file_bytes = await file.read()
    
    # Проверяем размер (до сжатия)
    if len(file_bytes) > 5 * 1024 * 1024:  # 5MB до сжатия
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Файл слишком большой. Максимум 5MB"
        )
    
    # Сохраняем старый URL для удаления
    old_avatar_url = profile.avatar_url
    
    try:
        # Загружаем новую аватарку
        new_avatar_url = await upload_avatar(file_bytes, user.id)
        
        # Обновляем профиль
        profile.avatar_url = new_avatar_url
        await db.commit()
        await db.refresh(profile)
        
        # Удаляем старую аватарку (не критично если не удалится)
        if old_avatar_url:
            await delete_avatar(old_avatar_url)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    
    return ProfileResponse(
        id=user.id,
        email=user.email,
        username=profile.username,
        role=profile.role,
        bio=profile.bio,
        avatar_url=profile.avatar_url
    )

print("✅ Profile router инициализирован")