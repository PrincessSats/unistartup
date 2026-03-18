from datetime import timedelta
import logging
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import hash_password
from app.config import settings
from app.database import get_db
from app.models.user import (
    AuthRegistrationFlow,
    User,
    UserAuthIdentity,
    UserProfile,
    UserRating,
    UserRegistrationData,
)
from app.schemas.user import (
    EmailRegistrationActionResponse,
    EmailRegistrationResendRequest,
    EmailRegistrationStartRequest,
    RegistrationCompleteRequest,
    RegistrationFlowResponse,
    Token,
)
from app.security.rate_limit import RateLimit, enforce_rate_limit
from app.services.auth_sessions import build_token_response, issue_login_session, set_refresh_cookie, utcnow
from app.services.registration import (
    MAGIC_LINK_MAX_SENDS,
    MAGIC_LINK_RESEND_COOLDOWN_SECONDS,
    OAUTH_FLOW_TTL_MINUTES,
    build_frontend_hash_url,
    build_github_authorize_url,
    build_magic_link_callback_url,
    build_registration_flow_token,
    build_yandex_authorize_url,
    decode_registration_flow_token,
    ensure_questionnaire_payload,
    exchange_github_code_for_token,
    exchange_yandex_code_for_token,
    fetch_github_profile,
    fetch_yandex_profile,
    generate_opaque_token,
    generate_pkce_pair,
    hash_secret_token,
    normalize_email,
    resolve_backend_yandex_callback_url,
    send_magic_link_email,
    validate_registration_password,
)

router = APIRouter(prefix="/api/auth", tags=["Регистрация и OAuth"])
logger = logging.getLogger(__name__)


def _get_request_host(request: Request) -> str:
    forwarded_host = str(request.headers.get("x-forwarded-host") or "").strip()
    if forwarded_host:
        return forwarded_host.split(",")[0].strip()
    host = str(request.headers.get("host") or "").strip()
    if host:
        return host
    if request.url.hostname:
        return request.url.hostname
    return ""


def _get_request_scheme(request: Request) -> str:
    forwarded_proto = str(request.headers.get("x-forwarded-proto") or "").strip()
    if forwarded_proto:
        return forwarded_proto.split(",")[0].strip()
    if request.url.scheme:
        return request.url.scheme
    return "https"


def _build_flow_token(flow: AuthRegistrationFlow) -> str:
    return build_registration_flow_token(flow.id, expires_at=flow.expires_at)


def _is_expired(value) -> bool:
    return value is not None and value <= utcnow()


def _flow_error_redirect(request: Request, *, route_path: str, error_code: str) -> RedirectResponse:
    redirect_url = build_frontend_hash_url(
        request_host=_get_request_host(request),
        route_path=route_path,
        params={"error": error_code},
    )
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)


async def _get_flow_or_raise(db: AsyncSession, flow_token: str) -> AuthRegistrationFlow:
    flow_id = decode_registration_flow_token(flow_token)
    if flow_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Поток регистрации не найден.")

    flow = await db.get(AuthRegistrationFlow, flow_id)
    if flow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Поток регистрации не найден.")
    if _is_expired(flow.expires_at):
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Поток регистрации истёк.")
    if flow.completed_user_id is not None or flow.consumed_at is not None:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Поток регистрации уже завершён.")
    return flow


def _ensure_email_delivery_configured() -> None:
    if not settings.YANDEX_MAIL_LOGIN or not settings.YANDEX_MAIL_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не настроены Yandex SMTP credentials для magic-link.",
        )
    if not settings.smtp_from_address:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не настроен адрес отправителя для magic-link.",
        )


def _ensure_yandex_oauth_configured() -> None:
    if not settings.YANDEX_CLIENT_ID or not settings.YANDEX_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не настроены Yandex OAuth credentials.",
        )


def _ensure_github_oauth_configured() -> None:
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не настроены GitHub OAuth credentials.",
        )


async def _finalize_social_oauth_flow(
    *,
    request: Request,
    db: AsyncSession,
    flow: AuthRegistrationFlow,
    provider: str,
    provider_user_id: str,
    email: str,
    login: Optional[str],
    avatar_url: Optional[str],
    raw_profile: dict,
) -> RedirectResponse:
    request_host = _get_request_host(request)
    now = utcnow()

    flow.email = email
    flow.email_verified_at = now
    flow.provider = provider
    flow.provider_user_id = provider_user_id
    flow.provider_email = email
    flow.provider_login = login
    flow.provider_avatar_url = avatar_url
    flow.provider_raw_profile_json = raw_profile
    flow.oauth_state_hash = None
    flow.oauth_code_verifier = None
    flow.expires_at = now + timedelta(hours=settings.MAGIC_LINK_TTL_HOURS)

    identity_result = await db.execute(
        select(UserAuthIdentity).where(
            UserAuthIdentity.provider == provider,
            UserAuthIdentity.provider_user_id == provider_user_id,
        )
    )
    identity = identity_result.scalar_one_or_none()

    user = None
    if identity is not None:
        user = await db.get(User, identity.user_id)
    if user is None:
        user_result = await db.execute(select(User).where(User.email == email))
        user = user_result.scalar_one_or_none()

    if user is not None:
        if user.is_active is None:
            user.is_active = True
        if user.is_active is False:
            flow.consumed_at = now
            await db.commit()
            return _flow_error_redirect(request, route_path="/login", error_code="account_blocked")

        if user.email_verified_at is None:
            user.email_verified_at = now

        if identity is None:
            identity = UserAuthIdentity(
                user_id=user.id,
                provider=provider,
                provider_user_id=provider_user_id,
                provider_email=email,
                provider_login=login,
                provider_avatar_url=avatar_url,
                raw_profile_json=raw_profile,
                last_login_at=now,
            )
            db.add(identity)
        else:
            identity.provider_email = email
            identity.provider_login = login
            identity.provider_avatar_url = avatar_url
            identity.raw_profile_json = raw_profile
            identity.last_login_at = now

        if avatar_url:
            profile_result = await db.execute(
                select(UserProfile).where(UserProfile.user_id == user.id)
            )
            profile = profile_result.scalar_one_or_none()
            if profile is not None and not profile.avatar_url:
                profile.avatar_url = avatar_url

        flow.completed_user_id = user.id
        flow.consumed_at = now
        refresh_token, _, _, _ = await issue_login_session(
            request=request,
            db=db,
            user=user,
        )

        redirect = RedirectResponse(
            url=build_frontend_hash_url(
                request_host=request_host,
                route_path="/auth/bridge",
                params={"provider": provider},
            ),
            status_code=status.HTTP_303_SEE_OTHER,
        )
        set_refresh_cookie(redirect, refresh_token)
        return redirect

    await db.commit()
    redirect_url = build_frontend_hash_url(
        request_host=request_host,
        route_path="/register",
        params={"flow_token": _build_flow_token(flow)},
    )
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.post(
    "/registration/email/start",
    response_model=EmailRegistrationActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_email_registration(
    payload: EmailRegistrationStartRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    enforce_rate_limit(
        request,
        scope="auth_register_email_ip",
        subject="any",
        rule=RateLimit(max_requests=20, window_seconds=3600),
    )
    enforce_rate_limit(
        request,
        scope="auth_register_email_account",
        subject=normalize_email(payload.email),
        rule=RateLimit(max_requests=5, window_seconds=1800),
    )

    if not payload.terms_accepted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нужно принять условия пользования.")

    _ensure_email_delivery_configured()

    normalized_email = normalize_email(payload.email)
    existing_user = await db.execute(select(User.id).where(User.email == normalized_email))
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email уже зарегистрирован.")

    now = utcnow()
    magic_link_token = generate_opaque_token()
    flow = AuthRegistrationFlow(
        intent="register",
        source="email_magic_link",
        email=normalized_email,
        terms_accepted_at=now,
        marketing_opt_in=payload.marketing_opt_in,
        marketing_opt_in_at=now if payload.marketing_opt_in else None,
        magic_link_token_hash=hash_secret_token(magic_link_token),
        magic_link_expires_at=now + timedelta(hours=settings.MAGIC_LINK_TTL_HOURS),
        magic_link_sent_count=1,
        last_magic_link_sent_at=now,
        expires_at=now + timedelta(hours=settings.MAGIC_LINK_TTL_HOURS),
    )
    db.add(flow)
    await db.flush()

    magic_link_url = build_magic_link_callback_url(
        request_scheme=_get_request_scheme(request),
        request_host=_get_request_host(request),
        token=magic_link_token,
    )
    try:
        await send_magic_link_email(to_email=normalized_email, magic_link_url=magic_link_url)
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.exception("Failed to send registration magic link to %s", normalized_email)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось отправить письмо. Попробуйте позже.",
        ) from exc

    await db.commit()

    return EmailRegistrationActionResponse(
        message="Письмо со ссылкой отправлено.",
        flow_token=_build_flow_token(flow),
        email=normalized_email,
    )


@router.post("/registration/email/resend", response_model=EmailRegistrationActionResponse)
async def resend_email_registration_link(
    payload: EmailRegistrationResendRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    _ensure_email_delivery_configured()
    flow = await _get_flow_or_raise(db, payload.flow_token)

    if flow.source != "email_magic_link":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный тип потока регистрации.")
    if flow.email_verified_at is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Почта уже подтверждена.")

    now = utcnow()
    if flow.last_magic_link_sent_at and (now - flow.last_magic_link_sent_at).total_seconds() < MAGIC_LINK_RESEND_COOLDOWN_SECONDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Письмо уже отправлено недавно. Попробуйте чуть позже.",
        )
    if int(flow.magic_link_sent_count or 0) >= MAGIC_LINK_MAX_SENDS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Превышено число повторных отправок magic-link.",
        )

    magic_link_token = generate_opaque_token()
    flow.magic_link_token_hash = hash_secret_token(magic_link_token)
    flow.magic_link_expires_at = now + timedelta(hours=settings.MAGIC_LINK_TTL_HOURS)
    flow.last_magic_link_sent_at = now
    flow.magic_link_sent_count = int(flow.magic_link_sent_count or 0) + 1

    magic_link_url = build_magic_link_callback_url(
        request_scheme=_get_request_scheme(request),
        request_host=_get_request_host(request),
        token=magic_link_token,
    )
    try:
        await send_magic_link_email(to_email=flow.email or "", magic_link_url=magic_link_url)
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.exception("Failed to resend registration magic link to %s", flow.email)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Не удалось отправить письмо повторно. Попробуйте позже.",
        ) from exc

    await db.commit()

    return EmailRegistrationActionResponse(
        message="Письмо отправлено повторно.",
        flow_token=_build_flow_token(flow),
        email=flow.email or "",
    )


@router.get("/registration/email/callback")
async def complete_email_magic_link(
    request: Request,
    token: str = Query(..., min_length=20),
    db: AsyncSession = Depends(get_db),
):
    token_hash = hash_secret_token(token)
    result = await db.execute(
        select(AuthRegistrationFlow).where(AuthRegistrationFlow.magic_link_token_hash == token_hash)
    )
    flow = result.scalar_one_or_none()
    if flow is None:
        return _flow_error_redirect(request, route_path="/register", error_code="invalid_magic_link")
    if flow.completed_user_id is not None or flow.consumed_at is not None:
        return _flow_error_redirect(request, route_path="/register", error_code="registration_already_completed")
    if _is_expired(flow.expires_at) or _is_expired(flow.magic_link_expires_at):
        return _flow_error_redirect(request, route_path="/register", error_code="expired_magic_link")

    now = utcnow()
    flow.email_verified_at = now
    flow.magic_link_consumed_at = now
    flow.magic_link_token_hash = None
    await db.commit()

    redirect_url = build_frontend_hash_url(
        request_host=_get_request_host(request),
        route_path="/register",
        params={"flow_token": _build_flow_token(flow)},
    )
    return RedirectResponse(url=redirect_url, status_code=status.HTTP_303_SEE_OTHER)


@router.get("/yandex/start")
async def start_yandex_oauth(
    request: Request,
    intent: str = Query(default="login"),
    terms_accepted: bool = Query(default=False),
    marketing_opt_in: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    _ensure_yandex_oauth_configured()
    normalized_intent = "register" if str(intent).strip().lower() == "register" else "login"
    if normalized_intent == "register" and not terms_accepted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нужно принять условия пользования.")

    state = generate_opaque_token()
    code_verifier, code_challenge = generate_pkce_pair()
    now = utcnow()
    flow = AuthRegistrationFlow(
        intent=normalized_intent,
        source="yandex",
        provider="yandex",
        terms_accepted_at=now if normalized_intent == "register" else None,
        marketing_opt_in=marketing_opt_in if normalized_intent == "register" else False,
        marketing_opt_in_at=now if normalized_intent == "register" and marketing_opt_in else None,
        oauth_state_hash=hash_secret_token(state),
        oauth_code_verifier=code_verifier,
        expires_at=now + timedelta(minutes=OAUTH_FLOW_TTL_MINUTES),
    )
    db.add(flow)
    await db.commit()

    authorize_url = build_yandex_authorize_url(
        client_id=settings.YANDEX_CLIENT_ID,
        redirect_uri=resolve_backend_yandex_callback_url(
            request_scheme=_get_request_scheme(request),
            request_host=_get_request_host(request),
        ),
        scope=settings.YANDEX_OAUTH_SCOPES,
        state=state,
        code_challenge=code_challenge,
    )
    return RedirectResponse(url=authorize_url, status_code=status.HTTP_302_FOUND)


@router.get("/github/start")
async def start_github_oauth(
    request: Request,
    intent: str = Query(default="login"),
    terms_accepted: bool = Query(default=False),
    marketing_opt_in: bool = Query(default=False),
    db: AsyncSession = Depends(get_db),
):
    _ensure_github_oauth_configured()
    normalized_intent = "register" if str(intent).strip().lower() == "register" else "login"
    if normalized_intent == "register" and not terms_accepted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нужно принять условия пользования.")

    state = generate_opaque_token()
    now = utcnow()
    flow = AuthRegistrationFlow(
        intent=normalized_intent,
        source="github",
        provider="github",
        terms_accepted_at=now if normalized_intent == "register" else None,
        marketing_opt_in=marketing_opt_in if normalized_intent == "register" else False,
        marketing_opt_in_at=now if normalized_intent == "register" and marketing_opt_in else None,
        oauth_state_hash=hash_secret_token(state),
        expires_at=now + timedelta(minutes=OAUTH_FLOW_TTL_MINUTES),
    )
    db.add(flow)
    await db.commit()

    authorize_url = build_github_authorize_url(
        client_id=settings.GITHUB_CLIENT_ID,
        redirect_uri=f"{resolve_backend_yandex_callback_url(request_scheme=_get_request_scheme(request), request_host=_get_request_host(request)).replace('/yandex/callback', '/github/callback')}",
        scope=settings.GITHUB_OAUTH_SCOPES,
        state=state,
    )
    return RedirectResponse(url=authorize_url, status_code=status.HTTP_302_FOUND)


@router.get("/yandex/callback")
async def yandex_oauth_callback(
    request: Request,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    request_host = _get_request_host(request)
    request_scheme = _get_request_scheme(request)
    if error:
        return _flow_error_redirect(request, route_path="/login", error_code=f"yandex_{error}")
    if not code or not state:
        return _flow_error_redirect(request, route_path="/login", error_code="yandex_missing_code")

    state_hash = hash_secret_token(state)
    result = await db.execute(select(AuthRegistrationFlow).where(AuthRegistrationFlow.oauth_state_hash == state_hash))
    flow = result.scalar_one_or_none()
    if flow is None or _is_expired(flow.expires_at) or flow.consumed_at is not None:
        return _flow_error_redirect(request, route_path="/login", error_code="yandex_state_invalid")

    try:
        token_payload = await exchange_yandex_code_for_token(
            code=code,
            code_verifier=flow.oauth_code_verifier or "",
            redirect_uri=resolve_backend_yandex_callback_url(
                request_scheme=request_scheme,
                request_host=request_host,
            ),
        )
        oauth_access_token = str(token_payload.get("access_token") or "").strip()
        if not oauth_access_token:
            raise ValueError("Yandex token response missing access_token")
        yandex_profile = await fetch_yandex_profile(oauth_access_token)
    except (httpx.HTTPError, ValueError) as exc:
        logger.exception("Yandex OAuth exchange failed")
        return _flow_error_redirect(
            request,
            route_path="/register" if flow.intent == "register" else "/login",
            error_code="yandex_oauth_failed",
        )

    return await _finalize_social_oauth_flow(
        request=request,
        db=db,
        flow=flow,
        provider="yandex",
        provider_user_id=yandex_profile.provider_user_id,
        email=yandex_profile.email,
        login=yandex_profile.login,
        avatar_url=yandex_profile.avatar_url,
        raw_profile=yandex_profile.raw_profile,
    )


@router.get("/github/callback")
async def github_oauth_callback(
    request: Request,
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    request_host = _get_request_host(request)
    request_scheme = _get_request_scheme(request)
    if error:
        return _flow_error_redirect(request, route_path="/login", error_code=f"github_{error}")
    if not code or not state:
        return _flow_error_redirect(request, route_path="/login", error_code="github_missing_code")

    state_hash = hash_secret_token(state)
    result = await db.execute(select(AuthRegistrationFlow).where(AuthRegistrationFlow.oauth_state_hash == state_hash))
    flow = result.scalar_one_or_none()
    if flow is None or _is_expired(flow.expires_at) or flow.consumed_at is not None:
        return _flow_error_redirect(request, route_path="/login", error_code="github_state_invalid")

    redirect_uri = f"{resolve_backend_yandex_callback_url(request_scheme=request_scheme, request_host=request_host).replace('/yandex/callback', '/github/callback')}"
    try:
        token_payload = await exchange_github_code_for_token(
            code=code,
            redirect_uri=redirect_uri,
        )
        oauth_access_token = str(token_payload.get("access_token") or "").strip()
        if not oauth_access_token:
            raise ValueError("GitHub token response missing access_token")
        github_profile = await fetch_github_profile(oauth_access_token)
    except (httpx.HTTPError, ValueError) as exc:
        logger.exception("GitHub OAuth exchange failed")
        return _flow_error_redirect(
            request,
            route_path="/register" if flow.intent == "register" else "/login",
            error_code="github_oauth_failed",
        )

    return await _finalize_social_oauth_flow(
        request=request,
        db=db,
        flow=flow,
        provider="github",
        provider_user_id=github_profile.provider_user_id,
        email=github_profile.email,
        login=github_profile.login,
        avatar_url=github_profile.avatar_url,
        raw_profile=github_profile.raw_profile,
    )


@router.get("/registration/flow", response_model=RegistrationFlowResponse)
async def get_registration_flow(
    flow_token: str = Query(..., min_length=16),
    db: AsyncSession = Depends(get_db),
):
    flow = await _get_flow_or_raise(db, flow_token)
    if not flow.email:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Email для потока регистрации не найден.")

    email_verified = flow.email_verified_at is not None
    step = "details" if email_verified or flow.source != "email_magic_link" else "email_sent"

    return RegistrationFlowResponse(
        flow_token=flow_token,
        source=flow.source,
        intent=flow.intent,
        email=flow.email,
        email_verified=email_verified,
        step=step,
        provider=flow.provider,
        username_suggestion=flow.provider_login,
        terms_accepted=flow.terms_accepted_at is not None,
        marketing_opt_in=bool(flow.marketing_opt_in),
    )


@router.post("/registration/complete", response_model=Token)
async def complete_registration(
    payload: RegistrationCompleteRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    flow = await _get_flow_or_raise(db, payload.flow_token)
    if not flow.email or flow.email_verified_at is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Почта должна быть подтверждена перед завершением регистрации.",
        )

    existing_user = await db.execute(select(User.id).where(User.email == flow.email))
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email уже зарегистрирован.")

    existing_username = await db.execute(select(UserProfile.user_id).where(UserProfile.username == payload.username))
    if existing_username.scalar_one_or_none() is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username уже занят.")

    password_hash = None
    if flow.source == "email_magic_link":
        if not payload.password:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нужно задать пароль для регистрации по email.")
        password_issues = validate_registration_password(
            payload.password,
            username=payload.username,
            email=flow.email,
            provider_login=flow.provider_login,
        )
        if password_issues:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=password_issues[0])
        password_hash = hash_password(payload.password)
    else:
        # OAuth-пользователь не задаёт локальный пароль на этапе регистрации.
        # Храним недоступный пользователю случайный hash, чтобы сохранить совместимость со старой схемой users.password_hash NOT NULL.
        password_hash = hash_password(generate_opaque_token())

    try:
        profession_tags, grade, interest_tags = ensure_questionnaire_payload(
            profession_tags=payload.profession_tags,
            grade=payload.grade,
            interest_tags=payload.interest_tags,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    now = utcnow()
    user = User(
        email=flow.email,
        password_hash=password_hash,
        is_active=True,
    )
    db.add(user)
    await db.flush()
    user.email_verified_at = flow.email_verified_at

    profile = UserProfile(
        user_id=user.id,
        username=payload.username,
        role="participant",
        avatar_url=flow.provider_avatar_url if flow.source in {"yandex", "github"} else None,
        onboarding_status="pending",
    )
    rating = UserRating(user_id=user.id)
    registration_data = UserRegistrationData(
        user_id=user.id,
        registration_source=flow.source,
        terms_accepted_at=flow.terms_accepted_at or now,
        marketing_opt_in=bool(flow.marketing_opt_in),
        marketing_opt_in_at=flow.marketing_opt_in_at,
        profession_tags=profession_tags,
        grade=grade,
        interest_tags=interest_tags,
        questionnaire_completed_at=now,
    )
    db.add(profile)
    db.add(rating)
    db.add(registration_data)

    if flow.source in {"yandex", "github"} and flow.provider and flow.provider_user_id:
        db.add(
            UserAuthIdentity(
                user_id=user.id,
                provider=flow.provider,
                provider_user_id=flow.provider_user_id,
                provider_email=flow.provider_email or flow.email,
                provider_login=flow.provider_login,
                provider_avatar_url=flow.provider_avatar_url,
                raw_profile_json=flow.provider_raw_profile_json,
                last_login_at=now,
            )
        )

    flow.completed_user_id = user.id
    flow.consumed_at = now

    await db.flush()
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
