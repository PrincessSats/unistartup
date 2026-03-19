from datetime import datetime, timedelta, timezone

from fastapi import Request, Response
from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import build_access_token, generate_refresh_token, hash_refresh_token
from app.config import settings
from app.models.user import AuthRefreshToken, User, UserProfile
from app.schemas.user import Token


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_dt(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_client_ip(request: Request) -> str:
    forwarded_for = str(request.headers.get("x-forwarded-for") or "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return ""


def set_refresh_cookie(response: Response, token: str) -> None:
    secure_cookie = bool(settings.REFRESH_TOKEN_COOKIE_SECURE)
    cross_site = settings.REFRESH_TOKEN_COOKIE_SAMESITE == "none"
    if cross_site:
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
    # Add Partitioned attribute for cross-site (SameSite=None) cookies to satisfy
    # Chrome CHIPS requirement and suppress "foreign cookie" warnings.
    if cross_site:
        for i, (name, value) in enumerate(response.raw_headers):
            if name == b"set-cookie" and b"refresh_token=" in value:
                response.raw_headers[i] = (name, value + b"; Partitioned")
                break


def clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.REFRESH_TOKEN_COOKIE_NAME,
        path=settings.REFRESH_TOKEN_COOKIE_PATH,
        domain=settings.REFRESH_TOKEN_COOKIE_DOMAIN or None,
    )


def build_token_response(
    *,
    access_token: str,
    access_expires_at: datetime,
    session_expires_at: datetime,
) -> Token:
    now = utcnow()
    access_ttl_seconds = int(max(1, (normalize_dt(access_expires_at) - now).total_seconds()))
    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=access_ttl_seconds,
        session_expires_at=normalize_dt(session_expires_at),
    )


async def issue_login_session(
    *,
    request: Request,
    db: AsyncSession,
    user: User,
) -> tuple[str, str, datetime, datetime]:
    now = utcnow()
    refresh_token = generate_refresh_token()
    refresh_token_db = AuthRefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(refresh_token),
        expires_at=now + timedelta(hours=settings.REFRESH_TOKEN_EXPIRE_HOURS),
        created_at=now,
        last_used_at=now,
        user_agent=str(request.headers.get("user-agent") or "").strip()[:1024] or None,
        ip_address=get_client_ip(request)[:128] or None,
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
