from datetime import timedelta, datetime, timezone
import logging
import secrets
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.exc import ProgrammingError
from app.auth.security import (
    build_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.database import get_db, ensure_auth_schema_compatibility
from app.models.user import AuthRefreshToken, User, UserProfile, UserRating
from app.models.auth import PasswordResetToken
from app.schemas.user import (
    AuthMessage,
    UserRegister,
    UserLogin,
    Token,
    UserResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    MessageResponse,
)
from app.config import settings
from app.security.rate_limit import RateLimit, enforce_rate_limit, auth_forgot_password_email, auth_reset_password_ip, rate_limiter
from app.services.auth_sessions import (
    build_token_response,
    clear_refresh_cookie,
    get_client_ip,
    issue_login_session,
    normalize_dt,
    set_refresh_cookie,
    utcnow,
)
from app.services.registration import send_password_reset_email, validate_registration_password

router = APIRouter(prefix="/auth", tags=["Авторизация"])
logger = logging.getLogger(__name__)


def _is_missing_refresh_tokens_table_error(exc: Exception) -> bool:
    error_text = str(exc).lower()
    return (
        "auth_refresh_tokens" in error_text
        and ("undefinedtable" in error_text or "does not exist" in error_text or "relation" in error_text)
    )


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
        refresh_token, access_token, access_expires_at, session_expires_at = await issue_login_session(
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
        refresh_token, access_token, access_expires_at, session_expires_at = await issue_login_session(
            request=request,
            db=db,
            user=user,
        )

    set_refresh_cookie(response, refresh_token)
    return build_token_response(
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
        clear_refresh_cookie(response)
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
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Сессия истекла. Выполните вход снова.",
        )

    now = utcnow()
    if token_row.revoked_at is not None:
        logger.info("Refresh rejected: token id=%s already revoked", token_row.id)
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh токен отозван. Выполните вход снова.",
        )

    expires_at = normalize_dt(token_row.expires_at)
    if expires_at <= now:
        logger.info("Refresh rejected: token id=%s expired at=%s", token_row.id, expires_at.isoformat())
        token_row.revoked_at = now
        token_row.last_used_at = now
        await db.commit()
        clear_refresh_cookie(response)
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
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Пользователь не найден или заблокирован",
        )
    if user.is_active is False:
        logger.info("Refresh rejected: user missing or inactive for token id=%s", token_row.id)
        token_row.revoked_at = now
        token_row.last_used_at = now
        await db.commit()
        clear_refresh_cookie(response)
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
        ip_address=get_client_ip(request)[:128] or None,
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

    set_refresh_cookie(response, next_refresh_token)
    return build_token_response(
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
            token_row.revoked_at = utcnow()
            token_row.last_used_at = utcnow()
            await db.commit()

    clear_refresh_cookie(response)
    return AuthMessage(message="Сессия завершена")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    request_obj: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Request a password reset link. Returns 200 even if email not found (prevents email enumeration).
    Rate limited to 3 requests per email per hour.
    """
    # Get client IP for logging
    client_ip = request_obj.client.host if request_obj.client else "unknown"

    try:
        # Apply rate limit
        allowed, _ = rate_limiter.check(
            auth_forgot_password_email.key_func(request.email.lower()),
            RateLimit(
                max_requests=settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_COUNT,
                window_seconds=settings.PASSWORD_RESET_REQUEST_RATE_LIMIT_WINDOW,
            ),
        )
        if not allowed:
            # Still return 200 to prevent email enumeration
            logger.warning(f"Password reset rate limit exceeded for {request.email} from {client_ip}")
            return MessageResponse(message="Email sent")
    except Exception as e:
        logger.warning(f"Rate limit check error: {e}")
        return MessageResponse(message="Email sent")

    # Look up user by email (case-insensitive)
    stmt = select(User).where(User.email == request.email.lower())
    user = await db.scalar(stmt)

    if not user:
        # Return success even if user not found (email enumeration prevention)
        logger.info(f"Password reset request for non-existent email: {request.email}")
        return MessageResponse(message="Email sent")

    # Generate reset token
    plaintext_token = secrets.token_urlsafe(48)
    token_hash = hashlib.sha256(plaintext_token.encode()).hexdigest()

    # Create token record
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_TTL_MINUTES)
    reset_token = PasswordResetToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
    )
    db.add(reset_token)
    await db.commit()

    # Send email (async, don't wait)
    frontend_url = settings.BACKEND_CALLBACK_BASE_URL or "https://hacknet.tech"
    # Remove /api suffix if present for frontend URL
    if frontend_url.endswith("/api"):
        frontend_url = frontend_url[:-4]

    try:
        await send_password_reset_email(user.email, plaintext_token, frontend_base_url=frontend_url)
    except Exception as e:
        logger.error(f"Failed to send password reset email to {user.email}: {e}")
        # Still return success to client

    logger.info(f"Password reset requested for {user.email}")
    return MessageResponse(message="Email sent")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    request_obj: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Reset password using a valid reset token. Token is single-use.
    Revokes all refresh tokens for the user (logs them out everywhere).
    Rate limited to 5 requests per IP per minute.
    """
    # Get client IP for rate limiting
    client_ip = request_obj.client.host if request_obj.client else "unknown"

    # Check rate limit
    allowed, retry_after = rate_limiter.check(
        auth_reset_password_ip.key_func(client_ip),
        RateLimit(
            max_requests=settings.PASSWORD_RESET_CONFIRM_RATE_LIMIT_COUNT,
            window_seconds=settings.PASSWORD_RESET_CONFIRM_RATE_LIMIT_WINDOW,
        ),
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many requests. Try again in {retry_after} seconds."
        )

    # Validate new password
    try:
        issues = validate_registration_password(request.new_password)
        if issues:
            raise ValueError("; ".join(issues))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    # Hash the plaintext token to look up in DB
    token_hash = hashlib.sha256(request.token.encode()).hexdigest()

    # Find token
    stmt = select(PasswordResetToken).where(
        and_(
            PasswordResetToken.token_hash == token_hash,
            PasswordResetToken.used_at.is_(None),  # Not yet used
            PasswordResetToken.expires_at > datetime.now(timezone.utc),  # Not expired
        )
    )
    reset_token = await db.scalar(stmt)

    if not reset_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token."
        )

    # Mark token as used
    reset_token.used_at = datetime.now(timezone.utc)

    # Get user and update password
    user = await db.get(User, reset_token.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found.")

    user.password_hash = hash_password(request.new_password)

    # Revoke all refresh tokens for this user (log out all sessions)
    stmt_revoke = select(AuthRefreshToken).where(
        and_(
            AuthRefreshToken.user_id == user.id,
            AuthRefreshToken.revoked_at.is_(None),
        )
    )
    tokens_to_revoke = await db.scalars(stmt_revoke)
    for token in tokens_to_revoke:
        token.revoked_at = datetime.now(timezone.utc)

    await db.commit()

    logger.info(f"Password reset successful for {user.email}")
    return MessageResponse(message="Password reset successfully")
