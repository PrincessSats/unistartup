"""
API для работы с профилем пользователя.

Эндпоинты:
- GET /profile - получить свой профиль
- PUT /profile - обновить username
- PUT /profile/onboarding - обновить статус онбординга
- PUT /profile/email - сменить email  
- PUT /profile/password - сменить пароль
- POST /profile/avatar - загрузить аватарку
"""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from typing import Literal, Optional
import inspect
import logging

from app.database import get_db
from app.models.user import User, UserProfile, UserRating
from app.models.landing import PromoCode
from app.auth.security import hash_password, verify_password
from app.auth.dependencies import get_current_user
from app.schemas.landing import PromoCodeRedeemRequest
from app.services.storage import upload_avatar, delete_avatar
from app.services.landing_hunt import PROMO_SOURCE_LANDING_HUNT

router = APIRouter(prefix="/profile", tags=["Профиль"])
logger = logging.getLogger(__name__)


async def _maybe_await(value):
    """Позволяет вызывать как sync, так и async функции сервиса storage."""
    if inspect.isawaitable(value):
        return await value
    return value


# ========== Схемы (Pydantic модели) ==========

class ProfileResponse(BaseModel):
    """Ответ с данными профиля"""
    id: int
    email: str
    username: str
    role: str
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    onboarding_status: Optional[str] = None
    contest_rating: int = 0
    practice_rating: int = 0
    first_blood: int = 0
    has_redeemed_landing_promo: bool = False
    landing_promo_redeemed_at: Optional[datetime] = None
    
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


class UpdateOnboardingStatusRequest(BaseModel):
    """Запрос на обновление статуса онбординга."""
    status: Literal["dismissed", "completed"]


class MessageResponse(BaseModel):
    """Простой ответ с сообщением"""
    message: str


async def _get_ratings(db: AsyncSession, user_id: int) -> tuple[int, int, int]:
    result = await db.execute(
        select(UserRating).where(UserRating.user_id == user_id)
    )
    rating = result.scalar_one_or_none()
    if not rating:
        return 0, 0, 0
    return rating.contest_rating, rating.practice_rating, rating.first_blood


async def _get_landing_promo_state(db: AsyncSession, user_id: int) -> tuple[bool, Optional[datetime]]:
    result = await db.execute(
        select(PromoCode.redeemed_at)
        .where(
            PromoCode.redeemed_by_user_id == user_id,
            PromoCode.source == PROMO_SOURCE_LANDING_HUNT,
        )
        .order_by(PromoCode.redeemed_at.desc())
        .limit(1)
    )
    redeemed_at = result.scalar_one_or_none()
    return redeemed_at is not None, redeemed_at


def _build_profile_response(
    *,
    user: User,
    profile: UserProfile,
    contest_rating: int,
    practice_rating: int,
    first_blood: int,
    has_redeemed_landing_promo: bool = False,
    landing_promo_redeemed_at: Optional[datetime] = None,
) -> ProfileResponse:
    return ProfileResponse(
        id=user.id,
        email=user.email,
        username=profile.username,
        role=profile.role,
        bio=profile.bio,
        avatar_url=profile.avatar_url,
        onboarding_status=profile.onboarding_status,
        contest_rating=contest_rating,
        practice_rating=practice_rating,
        first_blood=first_blood,
        has_redeemed_landing_promo=has_redeemed_landing_promo,
        landing_promo_redeemed_at=landing_promo_redeemed_at,
    )


# ========== Эндпоинты ==========

@router.get("", response_model=ProfileResponse)
async def get_profile(
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить свой профиль.
    Требует авторизации (Authorization: Bearer).
    """
    user, profile = current_user_data
    
    contest_rating, practice_rating, first_blood = await _get_ratings(db, user.id)
    has_redeemed_landing_promo, landing_promo_redeemed_at = await _get_landing_promo_state(db, user.id)

    return _build_profile_response(
        user=user,
        profile=profile,
        contest_rating=contest_rating,
        practice_rating=practice_rating,
        first_blood=first_blood,
        has_redeemed_landing_promo=has_redeemed_landing_promo,
        landing_promo_redeemed_at=landing_promo_redeemed_at,
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
    user_id = user.id

    # Важно: get_current_user часто возвращает объекты из другого DB-сешена.
    # Перезагружаем их в текущем `db`, иначе commit/refresh могут не сработать.
    user = await db.get(User, user_id)
    result_profile = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result_profile.scalar_one()
    
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
    
    contest_rating, practice_rating, first_blood = await _get_ratings(db, user.id)
    has_redeemed_landing_promo, landing_promo_redeemed_at = await _get_landing_promo_state(db, user.id)

    return _build_profile_response(
        user=user,
        profile=profile,
        contest_rating=contest_rating,
        practice_rating=practice_rating,
        first_blood=first_blood,
        has_redeemed_landing_promo=has_redeemed_landing_promo,
        landing_promo_redeemed_at=landing_promo_redeemed_at,
    )


@router.put("/onboarding", response_model=ProfileResponse)
async def update_onboarding_status(
    data: UpdateOnboardingStatusRequest,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Обновить статус онбординга текущего пользователя.
    Допустимые статусы: dismissed, completed.
    """
    user, _profile = current_user_data
    user_id = user.id

    # Перезагружаем в текущем db-сешене.
    user = await db.get(User, user_id)
    result_profile = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result_profile.scalar_one()

    profile.onboarding_status = data.status
    await db.commit()
    await db.refresh(profile)

    contest_rating, practice_rating, first_blood = await _get_ratings(db, user.id)
    has_redeemed_landing_promo, landing_promo_redeemed_at = await _get_landing_promo_state(db, user.id)

    return _build_profile_response(
        user=user,
        profile=profile,
        contest_rating=contest_rating,
        practice_rating=practice_rating,
        first_blood=first_blood,
        has_redeemed_landing_promo=has_redeemed_landing_promo,
        landing_promo_redeemed_at=landing_promo_redeemed_at,
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
    user_id = user.id

    # Перезагружаем в текущем `db`
    user = await db.get(User, user_id)
    # profile тут не обязателен, но оставим одинаковый подход
    result_profile = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result_profile.scalar_one()
    
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
    user_id = user.id

    # Перезагружаем в текущем `db`
    user = await db.get(User, user_id)
    result_profile = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result_profile.scalar_one()
    
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
    user_id = user.id

    # Перезагружаем в текущем `db`
    user = await db.get(User, user_id)
    result_profile = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result_profile.scalar_one()
    
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
        new_avatar_url = await _maybe_await(upload_avatar(file_bytes, user.id))
        
        # Обновляем профиль
        profile.avatar_url = new_avatar_url
        await db.commit()
        await db.refresh(profile)
        
        # Удаляем старую аватарку (не критично если не удалится)
        if old_avatar_url:
            await _maybe_await(delete_avatar(old_avatar_url))
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception:
        logger.exception("Avatar upload failed for user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Ошибка загрузки аватара. Попробуйте позже."
        )
    
    contest_rating, practice_rating, first_blood = await _get_ratings(db, user.id)
    has_redeemed_landing_promo, landing_promo_redeemed_at = await _get_landing_promo_state(db, user.id)

    return _build_profile_response(
        user=user,
        profile=profile,
        contest_rating=contest_rating,
        practice_rating=practice_rating,
        first_blood=first_blood,
        has_redeemed_landing_promo=has_redeemed_landing_promo,
        landing_promo_redeemed_at=landing_promo_redeemed_at,
    )


@router.post("/promo/redeem", response_model=ProfileResponse)
async def redeem_promo_code(
    data: PromoCodeRedeemRequest,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, _profile = current_user_data
    user_id = user.id

    user = await db.get(User, user_id)
    result_profile = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result_profile.scalar_one()

    has_redeemed_landing_promo, landing_promo_redeemed_at = await _get_landing_promo_state(db, user.id)
    if has_redeemed_landing_promo:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Промокод лендинга уже был активирован в этом аккаунте",
        )

    normalized_code = str(data.code or "").strip().upper()
    if not normalized_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Введите промокод",
        )

    result = await db.execute(
        select(PromoCode).where(PromoCode.code == normalized_code).limit(1)
    )
    promo_code = result.scalar_one_or_none()
    if promo_code is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Промокод не найден",
        )

    now = datetime.now(timezone.utc)
    if promo_code.redeemed_at is not None or promo_code.redeemed_by_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Промокод уже использован",
        )

    expires_at = promo_code.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Срок действия промокода истёк",
        )

    result_rating = await db.execute(select(UserRating).where(UserRating.user_id == user_id))
    rating = result_rating.scalar_one_or_none()
    if rating is None:
        rating = UserRating(user_id=user_id)
        db.add(rating)
        await db.flush()

    promo_code.redeemed_by_user_id = user_id
    promo_code.redeemed_at = now
    rating.practice_rating = int(rating.practice_rating or 0) + int(promo_code.reward_points or 0)

    await db.commit()
    await db.refresh(rating)

    contest_rating, practice_rating, first_blood = await _get_ratings(db, user.id)
    has_redeemed_landing_promo, landing_promo_redeemed_at = await _get_landing_promo_state(db, user.id)

    return _build_profile_response(
        user=user,
        profile=profile,
        contest_rating=contest_rating,
        practice_rating=practice_rating,
        first_blood=first_blood,
        has_redeemed_landing_promo=has_redeemed_landing_promo,
        landing_promo_redeemed_at=landing_promo_redeemed_at,
    )
