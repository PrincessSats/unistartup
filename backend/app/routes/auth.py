from datetime import datetime, timedelta, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from sqlalchemy.exc import ProgrammingError
from app.database import get_db, ensure_auth_schema_compatibility
from app.models.user import AuthRefreshToken, User, UserProfile, UserRating
from app.schemas.user import AuthMessage, UserRegister, UserLogin, Token, UserResponse
from app.auth.security import (
    build_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.config import settings
from app.security.rate_limit import RateLimit, enforce_rate_limit

router = APIRouter(prefix="/auth", tags=["Авторизация"])
logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_dt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _get_client_ip(request: Request) -> str:
    forwarded_for = str(request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return ""


def _set_refresh_cookie(response: Response, token: str) -> None:
    secure_cookie = bool(settings.REFRESH_TOKEN_COOKIE_SECURE)
    if settings.REFRESH_TOKEN_COOKIE_SAMESITE == "none":
        secure_cookie = True

    response.set_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        value=token,
        max_age=settings.refresh_token_expire_seconds,
        expires=settings.refresh_token_expire_seconds,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
        domain=settings.REFRESH_TOKEN_COOKIE_DOMAIN or None,
        secure=secure_cookie,
        httponly=True,
        samesite=settings.REFRESH_TOKEN_COOKIE_SAMESITE,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
        domain=settings.REFRESH_TOKEN_COOKIE_DOMAIN or None,
    )


def _build_token_response(
    *,
    access_token: str,
    access_expires_at: datetime,
    session_expires_at: datetime,
) -> Token:
    now = _utcnow()
    access_ttl_seconds = int(max(1, (_normalize_dt(access_expires_at) - now).total_seconds()))
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=access_ttl_seconds,
        session_expires_at=_normalize_dt(session_expires_at),
    )


def _is_missing_refresh_tokens_table_error(exc: Exception) -> bool:
    error_text = str(exc).lower()
    return (
        "auth_refresh_tokens" in error_text
        and ("undefinedtable" in error_text or "does not exist" in error_text or "relation" in error_text)
    )


async def _issue_login_session(
    *,
    request: Request,
    db: AsyncSession,
    user: User,
) -> tuple[str, str, datetime, datetime]:
    now = _utcnow()
    refresh_token = generate_refresh_token()
    refresh_token_db = AuthRefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=now + timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS),
        created_at=now,
        last_used_at=now,
        user_agent=str(request.headers.get("user-agent") or "").strip()[:1024] or None,
        ip_address=_get_client_ip(request)[:128] or None,
    )
    db.add(refresh_token_db)

    access_token, access_expires_at = build_access_token(data={"sub": user.email})
    await db.execute(
        update(UserProfile)
        .where(UserProfile.user_id == user.id)
        .values(last_login=func.now())
    )
    await db.commit()
    return refresh_token, access_token, access_expires_at, refresh_token_db.expires_at

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """
    Регистрация нового пользователя.
    
    Что делаем:
    1. Проверяем, не занят ли email
    2. Проверяем, не занят ли username
    3. Хешируем пароль
    4. Создаем User и UserProfile
    5. Сохраняем в БД
    """
    
    # Проверяем email
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email уже зарегистрирован"
        )
    
    # Проверяем username
    result = await db.execute(select(UserProfile).where(UserProfile.username == user_data.username))
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username уже занят"
        )
    
    # Создаем пользователя
    new_user = User(
        email=user_data.email,
        password_hash=hash_password(user_data.password),
        is_active=True
    )
    db.add(new_user)
    await db.flush()  # Получаем ID пользователя
    
    # Создаем профиль
    new_profile = UserProfile(
        user_id=new_user.id,
        username=user_data.username,
        role="participant",  # По умолчанию обычный участник
        onboarding_status="pending",
    )
    db.add(new_profile)

    # Создаем стартовые рейтинги
    new_rating = UserRating(
        user_id=new_user.id
    )
    db.add(new_rating)
    await db.commit()
    await db.refresh(new_user)
    
    # Формируем ответ
    return UserResponse(
        id=new_user.id,
        email=new_user.email,
        username=new_profile.username,
        role=new_profile.role,
        is_active=new_user.is_active,
        created_at=new_user.created_at
    )

@router.post("/login", response_model=Token)
async def login(
    request: Request,
    response: Response,
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """
    Вход в систему.
    
    Что делаем:
    1. Ищем пользователя по email
    2. Проверяем пароль
    3. Создаем JWT токен
    4. Отдаем токен клиенту
    """
    
    enforce_rate_limit(
        request,
        scope="auth_login_ip",
        subject="any",
        # Serverless/edge can collapse clients to shared source IP.
        # Keep IP guard but with a safer high threshold to reduce false positives.
        rule=RateLimit(max_requests=200, window_seconds=60),
    )
    enforce_rate_limit(
        request,
        scope="auth_login_account",
        subject=user_data.email.lower(),
        rule=RateLimit(max_requests=8, window_seconds=300),
    )

    # Ищем пользователя
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    user = result.scalar_one_or_none()
    
    # Проверяем существование и пароль
    if not user or not verify_password(user_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный email или пароль"
        )
    
    # Блокируем только явно отключенный аккаунт.
    # Legacy-значение NULL (если осталось в старой БД) самовосстанавливаем в TRUE.
    # Без лишнего commit — изменение уйдёт с основной транзакцией _issue_login_session.
    if user.is_active is None:
        user.is_active = True
    if user.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Аккаунт заблокирован"
        )
    
    try:
        refresh_token, access_token, access_expires_at, session_expires_at = await _issue_login_session(
            request=request,
            db=db,
            user=user,
        )
    except ProgrammingError as exc:
        await db.rollback()
        if not _is_missing_refresh_tokens_table_error(exc):
            raise
        logger.warning(
            "auth_refresh_tokens table is missing during login; applying schema compatibility and retrying once"
        )
        await ensure_auth_schema_compatibility()
        refresh_token, access_token, access_expires_at, session_expires_at = await _issue_login_session(
            request=request,
            db=db,
            user=user,
        )

    _set_refresh_cookie(response, refresh_token)
    return _build_token_response(
        access_token=access_token,
        access_expires_at=access_expires_at,
        session_expires_at=session_expires_at,
    )


@router.post("/refresh", response_model=Token)
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    raw_refresh_token = str(request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME) or "").strip()
    if not raw_refresh_token:
        logger.info("Refresh rejected: cookie is missing")
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла. Выполните вход снова.",
        )

    token_hash = hash_refresh_token(raw_refresh_token)
    try:
        token_row = (
            await db.execute(
                select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
    except ProgrammingError as exc:
        await db.rollback()
        if not _is_missing_refresh_tokens_table_error(exc):
            raise
        logger.warning(
            "auth_refresh_tokens table is missing during refresh; applying schema compatibility"
        )
        await ensure_auth_schema_compatibility()
        token_row = (
            await db.execute(
                select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
            )
        ).scalar_one_or_none()
    if token_row is None:
        logger.info("Refresh rejected: token hash not found")
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла. Выполните вход снова.",
        )

    now = _utcnow()
    if token_row.revoked_at is not None:
        logger.info("Refresh rejected: token id=%s already revoked", token_row.id)
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh токен отозван. Выполните вход снова.",
        )

    expires_at = _normalize_dt(token_row.expires_at)
    if expires_at <= now:
        logger.info("Refresh rejected: token id=%s expired at=%s", token_row.id, expires_at.isoformat())
        token_row.revoked_at = now
        token_row.last_used_at = now
        await db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла. Выполните вход снова.",
        )

    user = await db.get(User, token_row.user_id)
    if not user:
        logger.info("Refresh rejected: user missing or inactive for token id=%s", token_row.id)
        token_row.revoked_at = now
        token_row.last_used_at = now
        await db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или заблокирован",
        )
    if user.is_active is False:
        logger.info("Refresh rejected: user missing or inactive for token id=%s", token_row.id)
        token_row.revoked_at = now
        token_row.last_used_at = now
        await db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или заблокирован",
        )

    # Rotation: старый refresh токен помечаем отозванным и связываем с новым.
    next_refresh_token = generate_refresh_token()
    next_refresh_row = AuthRefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(next_refresh_token),
        expires_at=now + timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS),
        created_at=now,
        last_used_at=now,
        user_agent=str(request.headers.get("user-agent") or "").strip()[:1024] or None,
        ip_address=_get_client_ip(request)[:128] or None,
    )
    db.add(next_refresh_row)
    await db.flush()

    token_row.revoked_at = now
    token_row.last_used_at = now
    token_row.rotated_to_id = next_refresh_row.id

    access_token, access_expires_at = build_access_token(data={"sub": user.email})
    await db.commit()

    logger.info(
        "Refresh rotated: old_token_id=%s new_token_id=%s user_id=%s",
        token_row.id,
        next_refresh_row.id,
        user.id,
    )

    _set_refresh_cookie(response, next_refresh_token)
    return _build_token_response(
        access_token=access_token,
        access_expires_at=access_expires_at,
        session_expires_at=next_refresh_row.expires_at,
    )


@router.post("/logout", response_model=AuthMessage)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    raw_refresh_token = str(request.cookies.get(settings.REFRESH_TOKEN_COOKIE_NAME) or "").strip()
    if raw_refresh_token:
        token_hash = hash_refresh_token(raw_refresh_token)
        try:
            token_row = (
                await db.execute(
                    select(AuthRefreshToken).where(AuthRefreshToken.token_hash == token_hash)
                )
            ).scalar_one_or_none()
        except ProgrammingError as exc:
            await db.rollback()
            if not _is_missing_refresh_tokens_table_error(exc):
                raise
            logger.warning(
                "auth_refresh_tokens table is missing during logout; applying schema compatibility"
            )
            await ensure_auth_schema_compatibility()
            token_row = None
        if token_row is not None and token_row.revoked_at is None:
            token_row.revoked_at = _utcnow()
            token_row.last_used_at = _utcnow()
            await db.commit()

    _clear_refresh_cookie(response)
    return AuthMessage(message="Сессия завершена")
