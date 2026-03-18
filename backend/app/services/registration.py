import base64
from functools import partial
import hashlib
import re
import secrets
import smtplib
import ssl
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from typing import Any, Iterable, Optional
from urllib.parse import urlencode

import anyio
import httpx
from jose import JWTError, jwt
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
    if is_local_request_host(request_host):
        return LOCAL_BACKEND_BASE_URL
    return f"https://{str(request_host or '').strip()}"


def resolve_backend_yandex_callback_url(*, request_scheme: str, request_host: str) -> str:
    base_url = resolve_backend_base_url(request_scheme=request_scheme, request_host=request_host)
    return f"{base_url}/api/auth/yandex/callback"


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


def build_magic_link_callback_url(*, request_scheme: str, request_host: str, token: str) -> str:
    base_url = resolve_backend_base_url(request_scheme=request_scheme, request_host=request_host)
    callback_url = f"{base_url}/api/auth/registration/email/callback"
    return f"{callback_url}?{urlencode({'token': token})}"


def _send_magic_link_email_sync(*, to_email: str, magic_link_url: str) -> None:
    message = EmailMessage()
    message["Subject"] = "Заверши регистрацию в HackNet"
    message["From"] = settings.smtp_from_address
    message["To"] = to_email
    message.set_content(
        "\n".join(
            [
                "Привет!",
                "",
                "Чтобы подтвердить почту и продолжить регистрацию в HackNet, открой ссылку:",
                magic_link_url,
                "",
                f"Ссылка действует {settings.MAGIC_LINK_TTL_HOURS} часа(ов).",
            ]
        )
    )

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
    issues: list[str] = []
    raw = str(password or "")
    if len(raw) < 8:
        issues.append("Пароль должен быть минимум 8 символов.")
    if not re.fullmatch(r"[\x21-\x7E]+", raw):
        issues.append("Пароль должен содержать только латиницу, цифры и спецсимволы без пробелов.")
    if not re.search(r"[A-Z]", raw):
        issues.append("Пароль должен содержать хотя бы одну заглавную букву.")
    if not re.search(r"\d", raw):
        issues.append("Пароль должен содержать хотя бы одну цифру.")
    if not re.search(r"[^A-Za-z0-9]", raw):
        issues.append("Пароль должен содержать хотя бы один специальный символ.")

    email_local = normalize_email(email).split("@", 1)[0] if email else ""
    for part in split_identity_parts(username, email_local, provider_login):
        if part and part in raw.lower():
            issues.append("Пароль не должен содержать личные данные из email или никнейма.")
            break

    if has_forbidden_sequence(raw):
        issues.append("Пароль не должен содержать простые последовательности или повторяющиеся символы.")

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
