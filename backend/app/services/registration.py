import base64
from functools import partial
import hashlib
import re
import secrets
import smtplib
import ssl
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import Any, Iterable, Optional
from urllib.parse import urlencode

import anyio
import httpx
from jose import JWTError, jwk as jose_jwk, jwt
from pydantic import BaseModel

from app.auth.security import hash_refresh_token
from app.config import settings

YANDEX_AUTHORIZE_URL = "https://oauth.yandex.ru/authorize"
YANDEX_TOKEN_URL = "https://oauth.yandex.ru/token"
YANDEX_INFO_URL = "https://login.yandex.ru/info"
GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"
GITHUB_EMAILS_URL = "https://api.github.com/user/emails"
TELEGRAM_AUTHORIZE_URL = "https://oauth.telegram.org/auth"
TELEGRAM_TOKEN_URL = "https://oauth.telegram.org/token"
TELEGRAM_JWKS_URL = "https://oauth.telegram.org/.well-known/jwks.json"
TELEGRAM_ISSUER = "https://oauth.telegram.org"
_TELEGRAM_JWKS_TTL = 3600.0
_telegram_jwks_cache: Optional[dict] = None
_telegram_jwks_fetched_at: float = 0.0

LOCAL_BACKEND_BASE_URL = "http://127.0.0.1:8000"
LOCAL_FRONTEND_URL = "http://127.0.0.1:3000"
PROD_FRONTEND_URL = "https://www.hacknet.tech"

REGISTRATION_FLOW_TOKEN_TYPE = "registration_flow"
MAGIC_LINK_RESEND_COOLDOWN_SECONDS = 30
MAGIC_LINK_MAX_SENDS = 5
OAUTH_FLOW_TTL_MINUTES = 30

PROFESSION_OPTIONS = (
    "Студент",
    "Хакер",
    "Разработчик",
    "Тестировщик",
    "Аналитик",
    "Специалист информационной безопасности",
    "Другое",
)

GRADE_OPTIONS = (
    "Новичок",
    "Junior",
    "Middle",
    "Senior",
    "Lead / Principal",
    "CISO / Руководитель",
)

INTEREST_OPTIONS = (
    "Веб",
    "Криптография",
    "Форензика",
    "Реверс-инжиниринг",
    "Стеганография",
    "OSINT",
    "PVN",
    "Pentest Machines",
    "Все варианты",
)


class YandexProfile(BaseModel):
    provider_user_id: str
    email: str
    login: Optional[str] = None
    avatar_url: Optional[str] = None
    raw_profile: dict[str, Any]


class GitHubProfile(BaseModel):
    provider_user_id: str
    email: str
    login: Optional[str] = None
    avatar_url: Optional[str] = None
    raw_profile: dict[str, Any]


class TelegramProfile(BaseModel):
    provider_user_id: str
    login: Optional[str] = None
    avatar_url: Optional[str] = None
    raw_profile: dict[str, Any]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def is_local_request_host(host: str) -> bool:
    normalized = str(host or "").strip().lower()
    return normalized.startswith("127.0.0.1") or normalized.startswith("localhost")


def normalize_request_scheme(scheme: str) -> str:
    normalized = str(scheme or "").strip().lower()
    if normalized in {"http", "https"}:
        return normalized
    return "https"


def resolve_backend_base_url(*, request_scheme: str, request_host: str) -> str:
    explicit = str(settings.BACKEND_CALLBACK_BASE_URL or "").strip().rstrip("/")
    if explicit:
        return explicit
    if is_local_request_host(request_host):
        return LOCAL_BACKEND_BASE_URL
    return f"https://{str(request_host or '').strip()}"


def resolve_backend_yandex_callback_url(*, request_scheme: str, request_host: str) -> str:
    base_url = resolve_backend_base_url(request_scheme=request_scheme, request_host=request_host)
    return f"{base_url}/api/auth/yandex/callback"


def resolve_backend_github_callback_url(*, request_scheme: str, request_host: str) -> str:
    base_url = resolve_backend_base_url(request_scheme=request_scheme, request_host=request_host)
    return f"{base_url}/api/auth/github/callback"


def resolve_frontend_base_url(request_host: str) -> str:
    return LOCAL_FRONTEND_URL if is_local_request_host(request_host) else PROD_FRONTEND_URL


def build_frontend_hash_url(
    *,
    request_host: str,
    route_path: str,
    params: Optional[dict[str, Any]] = None,
) -> str:
    query = urlencode(
        [(key, str(value)) for key, value in (params or {}).items() if value is not None and str(value) != ""]
    )
    suffix = f"?{query}" if query else ""
    return f"{resolve_frontend_base_url(request_host)}#{route_path}{suffix}"


def build_registration_flow_token(flow_id: int, *, expires_at: datetime) -> str:
    payload = {
        "type": REGISTRATION_FLOW_TOKEN_TYPE,
        "sub": str(flow_id),
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_registration_flow_token(token: str) -> Optional[int]:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None
    if payload.get("type") != REGISTRATION_FLOW_TOKEN_TYPE:
        return None
    try:
        return int(payload.get("sub"))
    except (TypeError, ValueError):
        return None


def generate_opaque_token() -> str:
    return secrets.token_urlsafe(48)


def hash_secret_token(token: str) -> str:
    return hash_refresh_token(token)


def generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(72)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("utf-8")).digest()).rstrip(b"=").decode("ascii")
    return verifier, challenge


def build_yandex_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    code_challenge: str,
) -> str:
    query = urlencode(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{YANDEX_AUTHORIZE_URL}?{query}"


def build_github_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
        }
    )
    return f"{GITHUB_AUTHORIZE_URL}?{query}"


async def exchange_yandex_code_for_token(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            YANDEX_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": settings.YANDEX_CLIENT_ID,
                "client_secret": settings.YANDEX_CLIENT_SECRET,
                "code_verifier": code_verifier,
                "redirect_uri": redirect_uri,
            },
            headers={"Accept": "application/json"},
        )
        response.raise_for_status()
        return response.json()


async def fetch_yandex_profile(access_token: str) -> YandexProfile:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.get(
            YANDEX_INFO_URL,
            params={"format": "json"},
            headers={
                "Authorization": f"OAuth {access_token}",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()

    provider_user_id = str(payload.get("id") or "").strip()
    email = normalize_email(payload.get("default_email") or "")
    if not email:
        emails = payload.get("emails")
        if isinstance(emails, list) and emails:
            email = normalize_email(emails[0])

    if not provider_user_id or not email:
        raise ValueError("Yandex profile does not contain required id/email")

    avatar_id = str(payload.get("default_avatar_id") or "").strip()
    avatar_url = None
    if avatar_id:
        avatar_url = f"https://avatars.yandex.net/get-yapic/{avatar_id}/islands-200"

    return YandexProfile(
        provider_user_id=provider_user_id,
        email=email,
        login=str(payload.get("login") or "").strip() or None,
        avatar_url=avatar_url,
        raw_profile=payload,
    )


async def exchange_github_code_for_token(
    *,
    code: str,
    redirect_uri: str,
) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            GITHUB_TOKEN_URL,
            data={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code,
                "redirect_uri": redirect_uri,
            },
            headers={
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()


async def fetch_github_profile(access_token: str) -> GitHubProfile:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "hacknet-platform",
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        user_response = await client.get(GITHUB_USER_URL, headers=headers)
        user_response.raise_for_status()
        payload = user_response.json()

        email = normalize_email(payload.get("email") or "")
        if not email:
            emails_response = await client.get(GITHUB_EMAILS_URL, headers=headers)
            emails_response.raise_for_status()
            emails_payload = emails_response.json()
            if isinstance(emails_payload, list):
                primary_verified = next(
                    (
                        item for item in emails_payload
                        if isinstance(item, dict) and item.get("primary") and item.get("verified") and item.get("email")
                    ),
                    None,
                )
                verified = next(
                    (
                        item for item in emails_payload
                        if isinstance(item, dict) and item.get("verified") and item.get("email")
                    ),
                    None,
                )
                fallback = next(
                    (
                        item for item in emails_payload
                        if isinstance(item, dict) and item.get("email")
                    ),
                    None,
                )
                selected = primary_verified or verified or fallback
                if isinstance(selected, dict):
                    email = normalize_email(selected.get("email") or "")

    provider_user_id = str(payload.get("id") or "").strip()
    if not provider_user_id or not email:
        raise ValueError("GitHub profile does not contain required id/email")

    return GitHubProfile(
        provider_user_id=provider_user_id,
        email=email,
        login=str(payload.get("login") or "").strip() or None,
        avatar_url=str(payload.get("avatar_url") or "").strip() or None,
        raw_profile=payload,
    )


def resolve_backend_telegram_callback_url(*, request_scheme: str, request_host: str) -> str:
    base_url = resolve_backend_base_url(request_scheme=request_scheme, request_host=request_host)
    return f"{base_url}/api/auth/telegram/callback"


def build_telegram_authorize_url(
    *,
    client_id: str,
    redirect_uri: str,
    scope: str,
    state: str,
    code_challenge: str,
) -> str:
    query = urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": scope,
            "state": state,
            "code_challenge": code_challenge,
            "code_challenge_method": "S256",
        }
    )
    return f"{TELEGRAM_AUTHORIZE_URL}?{query}"


async def _get_telegram_jwks() -> dict:
    global _telegram_jwks_cache, _telegram_jwks_fetched_at
    now = time.monotonic()
    if _telegram_jwks_cache is None or now - _telegram_jwks_fetched_at > _TELEGRAM_JWKS_TTL:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(TELEGRAM_JWKS_URL)
            resp.raise_for_status()
            _telegram_jwks_cache = resp.json()
            _telegram_jwks_fetched_at = now
    return _telegram_jwks_cache


async def exchange_telegram_code_for_token(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> dict[str, Any]:
    credentials = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            TELEGRAM_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": code_verifier,
            },
            headers={
                "Authorization": f"Basic {credentials}",
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        return response.json()


async def fetch_telegram_profile_from_id_token(*, id_token: str, client_id: str) -> TelegramProfile:
    jwks_data = await _get_telegram_jwks()

    try:
        header = jwt.get_unverified_header(id_token)
    except JWTError as exc:
        raise ValueError("Telegram id_token has invalid header") from exc

    kid = header.get("kid")
    keys = jwks_data.get("keys", [])
    matching_key_data: Optional[dict] = None
    if kid:
        matching_key_data = next((k for k in keys if k.get("kid") == kid), None)
    if matching_key_data is None and keys:
        matching_key_data = keys[0]
    if matching_key_data is None:
        raise ValueError("No suitable key found in Telegram JWKS")

    try:
        payload = jwt.decode(
            id_token,
            matching_key_data,
            algorithms=[header.get("alg", "RS256")],
            audience=str(client_id),
            issuer=TELEGRAM_ISSUER,
        )
    except JWTError as exc:
        raise ValueError(f"Telegram id_token validation failed: {exc}") from exc

    provider_user_id = str(payload.get("sub") or payload.get("id") or "").strip()
    if not provider_user_id:
        raise ValueError("Telegram id_token missing sub/id claim")

    preferred_username = str(payload.get("preferred_username") or "").strip()
    picture = str(payload.get("picture") or "").strip()
    name = str(payload.get("name") or "").strip()

    return TelegramProfile(
        provider_user_id=provider_user_id,
        login=preferred_username or None,
        avatar_url=picture or None,
        raw_profile={
            "sub": provider_user_id,
            "name": name or None,
            "preferred_username": preferred_username or None,
            "picture": picture or None,
        },
    )


def build_magic_link_callback_url(*, request_scheme: str, request_host: str, token: str) -> str:
    base_url = resolve_backend_base_url(request_scheme=request_scheme, request_host=request_host)
    callback_url = f"{base_url}/api/auth/registration/email/callback"
    return f"{callback_url}?{urlencode({'token': token})}"


def _send_magic_link_email_sync(*, to_email: str, magic_link_url: str) -> None:
    ttl = settings.MAGIC_LINK_TTL_HOURS

    plain = "\n".join([
        "Привет!",
        "",
        "Чтобы подтвердить почту и продолжить регистрацию в HackNet,",
        "нажми кнопку в письме или перейди по ссылке ниже:",
        "",
        magic_link_url,
        "",
        f"Ссылка действует {ttl} ч.",
        "",
        "Если ты не регистрировался — просто проигнорируй это письмо.",
    ])

    html = f"""<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f0f13;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f0f13;padding:40px 16px;">
    <tr><td align="center">
      <table width="100%" style="max-width:480px;background:#1a1a24;border-radius:16px;overflow:hidden;">
        <tr>
          <td style="background:linear-gradient(135deg,#8452ff,#5c6fff);padding:32px 40px;text-align:center;">
            <span style="font-size:28px;font-weight:700;color:#fff;letter-spacing:-0.5px;">HackNet</span>
          </td>
        </tr>
        <tr>
          <td style="padding:36px 40px;">
            <p style="margin:0 0 8px;font-size:22px;font-weight:600;color:#fff;">Подтверди почту</p>
            <p style="margin:0 0 28px;font-size:15px;line-height:1.6;color:rgba(255,255,255,0.6);">
              Нажми кнопку ниже, чтобы подтвердить адрес и продолжить регистрацию&nbsp;в&nbsp;HackNet.
            </p>
            <table cellpadding="0" cellspacing="0" style="margin:0 auto 28px;">
              <tr>
                <td align="center" style="background:linear-gradient(135deg,#8452ff,#5c6fff);border-radius:12px;">
                  <a href="{magic_link_url}"
                     style="display:inline-block;padding:14px 36px;font-size:15px;font-weight:600;color:#fff;text-decoration:none;letter-spacing:0.2px;">
                    Подтвердить почту
                  </a>
                </td>
              </tr>
            </table>
            <p style="margin:0 0 6px;font-size:13px;color:rgba(255,255,255,0.35);">
              Кнопка не работает? Скопируй ссылку в браузер:
            </p>
            <p style="margin:0;word-break:break-all;font-size:12px;color:rgba(255,255,255,0.25);">
              <a href="{magic_link_url}" style="color:rgba(255,255,255,0.25);">{magic_link_url}</a>
            </p>
          </td>
        </tr>
        <tr>
          <td style="padding:20px 40px 28px;border-top:1px solid rgba(255,255,255,0.06);">
            <p style="margin:0;font-size:12px;color:rgba(255,255,255,0.3);line-height:1.6;">
              Ссылка действует <strong style="color:rgba(255,255,255,0.45);">{ttl}&nbsp;ч.</strong><br>
              Если ты не регистрировался — просто проигнорируй это письмо.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

    message = EmailMessage()
    message["Subject"] = "Подтвердите почту — HackNet"
    message["From"] = settings.smtp_from_address
    message["To"] = to_email
    message.set_content(plain)
    message.add_alternative(html, subtype="html")

    if settings.SMTP_USE_SSL:
        context = ssl.create_default_context()
        with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=20) as server:
            server.login(settings.YANDEX_MAIL_LOGIN, settings.YANDEX_MAIL_PASSWORD)
            server.send_message(message)
        return

    with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
        server.starttls(context=ssl.create_default_context())
        server.login(settings.YANDEX_MAIL_LOGIN, settings.YANDEX_MAIL_PASSWORD)
        server.send_message(message)


async def send_magic_link_email(*, to_email: str, magic_link_url: str) -> None:
    await anyio.to_thread.run_sync(
        partial(
            _send_magic_link_email_sync,
            to_email=to_email,
            magic_link_url=magic_link_url,
        )
    )


def password_reset_email_template(reset_token: str, user_email: str, reset_link_url: str) -> tuple[str, str]:
    """
    Generate password reset email subject and HTML body.

    Args:
        reset_token: The plaintext reset token (for audit/logging, not sent)
        user_email: User's email address
        reset_link_url: Full URL to reset page with token (e.g., https://hacknet.tech/reset-password?token=xyz)

    Returns:
        (subject, html_body)
    """
    subject = "Восстановление пароля на HackNet"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0e27; color: #e0e0e0; margin: 0; padding: 20px; }}
            .container {{ max-width: 600px; margin: 0 auto; background: #1a1f3a; border-radius: 8px; padding: 40px; border: 1px solid #2a3050; }}
            .logo {{ text-align: center; margin-bottom: 30px; font-size: 24px; font-weight: bold; color: #00d4ff; }}
            .greeting {{ margin-bottom: 20px; font-size: 16px; }}
            .message {{ margin-bottom: 30px; line-height: 1.6; font-size: 14px; }}
            .button {{ display: inline-block; background: #00d4ff; color: #0a0e27; padding: 12px 32px; border-radius: 6px; text-decoration: none; font-weight: 600; margin: 20px 0; }}
            .expiry {{ margin-top: 20px; font-size: 12px; color: #999; }}
            .footer {{ margin-top: 40px; border-top: 1px solid #2a3050; padding-top: 20px; font-size: 12px; color: #666; text-align: center; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="logo">HackNet</div>

            <div class="greeting">Привет,</div>

            <div class="message">
                Вы запросили восстановление пароля. Нажмите на кнопку ниже, чтобы установить новый пароль:
            </div>

            <a href="{reset_link_url}" class="button">Сбросить пароль</a>

            <div class="expiry">
                ⏱️ Ссылка действительна 1 час. Если вы не запрашивали восстановление, проигнорируйте это письмо.
            </div>

            <div class="footer">
                <p>© 2026 HackNet. Все права защищены.</p>
            </div>
        </div>
    </body>
    </html>
    """

    return subject, html_body


def _send_password_reset_email_sync(user_email: str, reset_token: str, frontend_base_url: str = "https://hacknet.tech") -> bool:
    """
    Synchronously send password reset email via Yandex SMTP.

    Args:
        user_email: Recipient email
        reset_token: Plaintext reset token to include in link
        frontend_base_url: Base URL for reset link (e.g., https://hacknet.tech)

    Returns:
        True if sent successfully, False otherwise
    """
    try:
        reset_link_url = f"{frontend_base_url}/reset-password?token={reset_token}"
        subject, html_body = password_reset_email_template(reset_token, user_email, reset_link_url)

        msg = MIMEMultipart("alternative")
        msg["Subject"] = Header(subject, "utf-8")
        msg["From"] = settings.smtp_from_address
        msg["To"] = user_email

        msg.attach(MIMEText(html_body, "html", "utf-8"))

        if settings.SMTP_USE_SSL:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, context=context, timeout=20) as server:
                server.login(settings.YANDEX_MAIL_LOGIN, settings.YANDEX_MAIL_PASSWORD)
                server.sendmail(settings.smtp_from_address, user_email, msg.as_string())
            return True

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(settings.YANDEX_MAIL_LOGIN, settings.YANDEX_MAIL_PASSWORD)
            server.sendmail(settings.smtp_from_address, user_email, msg.as_string())

        return True
    except Exception as e:
        # Log the error without raising; caller should handle
        return False


async def send_password_reset_email(user_email: str, reset_token: str, frontend_base_url: str = "https://hacknet.tech") -> bool:
    """
    Async wrapper for password reset email sending.
    """
    return await anyio.to_thread.run_sync(
        _send_password_reset_email_sync,
        user_email,
        reset_token,
        frontend_base_url,
    )


def split_identity_parts(*values: Optional[str]) -> list[str]:
    parts: list[str] = []
    for value in values:
        raw = str(value or "").strip().lower()
        if not raw:
            continue
        for part in re.split(r"[^a-z0-9]+", raw):
            if len(part) >= 3:
                parts.append(part)
    # preserve order while removing duplicates
    unique_parts: list[str] = []
    for part in parts:
        if part not in unique_parts:
            unique_parts.append(part)
    return unique_parts


def has_forbidden_sequence(password: str) -> bool:
    normalized = str(password or "").lower()
    for source in ("abcdefghijklmnopqrstuvwxyz", "0123456789"):
        for length in range(4, 7):
            for index in range(0, len(source) - length + 1):
                chunk = source[index : index + length]
                if chunk in normalized or chunk[::-1] in normalized:
                    return True
    for char in set(normalized):
        if char and char * 4 in normalized:
            return True
    return False


def validate_registration_password(
    password: str,
    *,
    username: Optional[str] = None,
    email: Optional[str] = None,
    provider_login: Optional[str] = None,
) -> list[str]:
    """
    Validate password strength according to security requirements.
    
    Requirements:
    - Minimum 12 characters
    - At least one uppercase letter
    - At least one lowercase letter  
    - At least one digit
    - At least one special character
    - No personal information from username/email
    - No common patterns or sequences
    """
    issues: list[str] = []
    raw = str(password or "")
    
    # Check minimum length (12 characters for strong security)
    if len(raw) < 12:
        issues.append("Пароль должен быть минимум 12 символов.")
    
    # Check character set (ASCII printable, no spaces)
    if not re.fullmatch(r"[\x21-\x7E]+", raw):
        issues.append("Пароль должен содержать только латиницу, цифры и спецсимволы без пробелов.")
    
    # Require at least one uppercase letter
    if not re.search(r"[A-Z]", raw):
        issues.append("Пароль должен содержать хотя бы одну заглавную букву.")
    
    # Require at least one lowercase letter
    if not re.search(r"[a-z]", raw):
        issues.append("Пароль должен содержать хотя бы одну строчную букву.")
    
    # Require at least one digit
    if not re.search(r"\d", raw):
        issues.append("Пароль должен содержать хотя бы одну цифру.")
    
    # Require at least one special character
    if not re.search(r"[^A-Za-z0-9]", raw):
        issues.append("Пароль должен содержать хотя бы один специальный символ (!@#$%^&*()_+-=[]{}|;:,.<>?).")
    
    # Check for personal information in password
    email_local = normalize_email(email).split("@", 1)[0] if email else ""
    for part in split_identity_parts(username, email_local, provider_login):
        if part and len(part) >= 3 and part.lower() in raw.lower():
            issues.append("Пароль не должен содержать личные данные из email или никнейма.")
            break
    
    # Check for forbidden sequences and patterns
    if has_forbidden_sequence(raw):
        issues.append("Пароль не должен содержать простые последовательности или повторяющиеся символы.")
    
    # Check for common weak passwords
    common_weak_passwords = {
        "password", "qwerty", "123456", "12345678", "letmein", 
        "welcome", "admin", "login", "passw0rd", "hacknet"
    }
    if raw.lower() in common_weak_passwords:
        issues.append("Этот пароль слишком простой. Выберите более уникальный пароль.")
    
    # Check for keyboard patterns
    keyboard_patterns = ["qwerty", "asdf", "zxcv", "1234", "!@#$", "qazwsx"]
    for pattern in keyboard_patterns:
        if pattern in raw.lower():
            issues.append("Пароль не должен содержать клавиатурные паттерны (qwerty, asdf, etc.).")
            break
    
    return issues


def normalize_multi_select(values: Iterable[str], *, allowed: Iterable[str]) -> list[str]:
    allowed_set = {item for item in allowed}
    normalized: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item not in allowed_set or item in normalized:
            continue
        normalized.append(item)
    return normalized


def normalize_single_select(value: str, *, allowed: Iterable[str]) -> Optional[str]:
    item = str(value or "").strip()
    return item if item in set(allowed) else None


def ensure_questionnaire_payload(
    *,
    profession_tags: Iterable[str],
    grade: str,
    interest_tags: Iterable[str],
) -> tuple[list[str], str, list[str]]:
    normalized_professions = normalize_multi_select(profession_tags, allowed=PROFESSION_OPTIONS)
    normalized_grade = normalize_single_select(grade, allowed=GRADE_OPTIONS)
    normalized_interests = normalize_multi_select(interest_tags, allowed=INTEREST_OPTIONS)

    if not normalized_professions:
        raise ValueError("Нужно выбрать хотя бы один вариант в вопросе о профессии.")
    if not normalized_grade:
        raise ValueError("Нужно выбрать один вариант в вопросе о грейде.")
    if not normalized_interests:
        raise ValueError("Нужно выбрать хотя бы один вариант в вопросе об интересах.")

    return normalized_professions, normalized_grade, normalized_interests
