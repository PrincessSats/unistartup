"""
API для работы с профилем пользователя.

Эндпоинты:
- GET /profile - получить свой профиль
- PUT /profile - обновить username
- DELETE /profile - удалить аккаунт после подтверждения username
- PUT /profile/onboarding - обновить статус онбординга
- PUT /profile/email - сменить email  
- PUT /profile/password - сменить пароль
- POST /profile/avatar - загрузить аватарку
"""

from fastapi import APIRouter, Depends, HTTPException, Response, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete as sqlalchemy_delete, select, update
from pydantic import BaseModel, EmailStr
from typing import Literal, Optional
import inspect
import logging

from app.auth.dependencies import get_current_user
from app.auth.security import hash_password, verify_password
from app.database import get_db
from app.models.contest import LlmGeneration, PromptTemplate, Task
from app.models.user import User, UserProfile, UserRating
from app.services.auth_sessions import clear_refresh_cookie
from app.services.storage import upload_avatar, delete_avatar
from sqlalchemy import text

router = APIRouter(prefix="/profile", tags=["Профиль"])
logger = logging.getLogger(__name__)


async def _maybe_await(value):
    """Позволяет вызывать как sync, так и async функции сервиса storage."""
    if inspect.isawaitable(value):
        return await value
    return value


# ========== Схемы (Pydantic модели) ==========

class CurrentTariffInfo(BaseModel):
    """Информация о текущем тарифе пользователя"""
    code: str
    name: str
    is_promo: bool = False
    valid_to: Optional[str] = None
    monthly_price_rub: float = 0
    description: Optional[str] = None
    limits: dict = {}


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
    current_tariff: Optional[CurrentTariffInfo] = None

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


class DeleteAccountRequest(BaseModel):
    """Запрос на удаление аккаунта с подтверждением username."""
    username: str


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


async def _get_current_tariff(db: AsyncSession, user_id: int) -> Optional[CurrentTariffInfo]:
    """Получить текущий тариф пользователя."""
    result = await db.execute(
        text(
            """
            SELECT tp.code, tp.name, tp.monthly_price_rub, tp.description, tp.limits,
                   ut.is_promo, ut.valid_to
            FROM user_tariffs ut
            JOIN tariff_plans tp ON tp.id = ut.tariff_id
            WHERE ut.user_id = :user_id
              AND ut.valid_from <= now()
              AND (ut.valid_to IS NULL OR ut.valid_to > now())
            ORDER BY ut.valid_from DESC
            LIMIT 1
            """
        ),
        {"user_id": user_id},
    )
    row = result.mappings().first()
    if not row:
        return None

    valid_to = row["valid_to"]
    if valid_to:
        valid_to = valid_to.isoformat()

    return CurrentTariffInfo(
        code=row["code"],
        name=row["name"],
        is_promo=row["is_promo"],
        valid_to=valid_to,
        monthly_price_rub=float(row["monthly_price_rub"]),
        description=row["description"],
        limits=row["limits"] if row["limits"] else {},
    )


def _build_profile_response(
    *,
    user: User,
    profile: UserProfile,
    contest_rating: int,
    practice_rating: int,
    first_blood: int,
    current_tariff: Optional[CurrentTariffInfo] = None,
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
        current_tariff=current_tariff,
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
    current_tariff = await _get_current_tariff(db, user.id)

    return _build_profile_response(
        user=user,
        profile=profile,
        contest_rating=contest_rating,
        practice_rating=practice_rating,
        first_blood=first_blood,
        current_tariff=current_tariff,
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
    current_tariff = await _get_current_tariff(db, user.id)

    return _build_profile_response(
        user=user,
        profile=profile,
        contest_rating=contest_rating,
        practice_rating=practice_rating,
        first_blood=first_blood,
        current_tariff=current_tariff,
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
    current_tariff = await _get_current_tariff(db, user.id)

    return _build_profile_response(
        user=user,
        profile=profile,
        contest_rating=contest_rating,
        practice_rating=practice_rating,
        first_blood=first_blood,
        current_tariff=current_tariff,
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

    # Validate new password strength using the same validation as registration
    from app.services.registration import validate_registration_password
    password_issues = validate_registration_password(
        data.new_password,
        username=profile.username,
        email=user.email
    )
    if password_issues:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=" ".join(password_issues)
        )

    # Обновляем пароль
    user.password_hash = hash_password(data.new_password)
    await db.commit()

    return MessageResponse(message="Пароль успешно изменён")


@router.delete("", response_model=MessageResponse)
async def delete_account(
    data: DeleteAccountRequest,
    response: Response,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Удалить текущий аккаунт после подтверждения username.
    """
    user, _profile = current_user_data
    user_id = user.id

    result_profile = await db.execute(select(UserProfile).where(UserProfile.user_id == user_id))
    profile = result_profile.scalar_one_or_none()
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Профиль не найден"
        )

    submitted_username = data.username.strip()
    current_username = (profile.username or "").strip()

    if not submitted_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Введите никнейм для подтверждения удаления"
        )

    if submitted_username != current_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Никнейм не совпадает"
        )

    avatar_url = profile.avatar_url

    await db.execute(
        update(Task)
        .where(Task.created_by == user_id)
        .values(created_by=None)
    )
    await db.execute(
        update(LlmGeneration)
        .where(LlmGeneration.created_by == user_id)
        .values(created_by=None)
    )
    await db.execute(
        update(PromptTemplate)
        .where(PromptTemplate.updated_by == user_id)
        .values(updated_by=None)
    )
    await db.execute(
        sqlalchemy_delete(User).where(User.id == user_id)
    )
    await db.commit()

    clear_refresh_cookie(response)

    if avatar_url:
        try:
            await _maybe_await(delete_avatar(avatar_url))
        except Exception:
            logger.warning("Avatar cleanup failed during account deletion for user_id=%s", user_id, exc_info=True)

    return MessageResponse(message="Аккаунт удалён")


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
    current_tariff = await _get_current_tariff(db, user.id)

    return _build_profile_response(
        user=user,
        profile=profile,
        contest_rating=contest_rating,
        practice_rating=practice_rating,
        first_blood=first_blood,
        current_tariff=current_tariff,
    )
