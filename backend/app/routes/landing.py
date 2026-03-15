from __future__ import annotations

from datetime import timedelta
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.landing import LandingHuntSession, LandingHuntSessionItem, PromoCode
from app.schemas.landing import (
    LandingHuntFoundRequest,
    LandingHuntResponse,
    LandingHuntSessionRequest,
)
from app.services.landing_hunt import (
    LANDING_HUNT_BUG_KEYS,
    PROMO_REWARD_POINTS,
    PROMO_SOURCE_LANDING_HUNT,
    PROMO_TTL,
    apply_found_bug,
    create_promo_code,
    create_session_token,
    is_valid_bug_key,
    normalize_bug_key,
    normalize_session_token,
    ordered_found_bug_keys,
    utcnow,
)

router = APIRouter(prefix="/landing", tags=["Лендинг"])
logger = logging.getLogger(__name__)


async def _find_session_by_token(db: AsyncSession, session_token: str) -> LandingHuntSession | None:
    if not session_token:
        return None
    result = await db.execute(
        select(LandingHuntSession).where(LandingHuntSession.session_token == session_token)
    )
    return result.scalar_one_or_none()


async def _load_found_bug_keys(db: AsyncSession, session_id: int) -> list[str]:
    result = await db.execute(
        select(LandingHuntSessionItem.bug_key).where(LandingHuntSessionItem.session_id == session_id)
    )
    return ordered_found_bug_keys(result.scalars().all())


async def _get_session_promo_code(db: AsyncSession, session_id: int) -> PromoCode | None:
    result = await db.execute(
        select(PromoCode).where(PromoCode.issued_hunt_session_id == session_id)
    )
    return result.scalar_one_or_none()


async def _create_session(db: AsyncSession) -> LandingHuntSession:
    session = LandingHuntSession(session_token=create_session_token())
    db.add(session)
    await db.flush()
    return session


async def _find_or_create_session(
    db: AsyncSession,
    *,
    session_token: str,
) -> LandingHuntSession:
    existing = await _find_session_by_token(db, session_token)
    if existing is not None:
        return existing
    return await _create_session(db)


async def _ensure_session_promo_code(db: AsyncSession, session: LandingHuntSession) -> PromoCode:
    existing = await _get_session_promo_code(db, session.id)
    if existing is not None:
        return existing

    for _ in range(20):
        candidate = PromoCode(
            code=create_promo_code(),
            source=PROMO_SOURCE_LANDING_HUNT,
            reward_points=PROMO_REWARD_POINTS,
            expires_at=utcnow() + PROMO_TTL,
            issued_hunt_session_id=session.id,
        )
        db.add(candidate)
        try:
            await db.flush()
            return candidate
        except IntegrityError:
            await db.rollback()
            session = await _find_session_by_token(db, session.session_token) or await _create_session(db)
            existing = await _get_session_promo_code(db, session.id)
            if existing is not None:
                return existing
            logger.warning("Promo code collision or race for landing session=%s, retrying", session.id)
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Не удалось выдать промокод. Попробуйте ещё раз.",
    )


async def _build_hunt_response(
    db: AsyncSession,
    *,
    session: LandingHuntSession,
    just_completed: bool = False,
) -> LandingHuntResponse:
    found_bug_keys = await _load_found_bug_keys(db, session.id)
    promo = await _get_session_promo_code(db, session.id)
    completed = len(found_bug_keys) == len(LANDING_HUNT_BUG_KEYS)
    return LandingHuntResponse(
        session_token=session.session_token,
        found_bug_keys=found_bug_keys,
        found_count=len(found_bug_keys),
        total_count=len(LANDING_HUNT_BUG_KEYS),
        completed=completed,
        promo_code=promo.code if promo else None,
        just_completed=just_completed,
    )


@router.post("/hunt/session", response_model=LandingHuntResponse)
async def create_or_restore_hunt_session(
    payload: LandingHuntSessionRequest,
    db: AsyncSession = Depends(get_db),
):
    session_token = normalize_session_token(payload.session_token)
    session = await _find_or_create_session(db, session_token=session_token)
    session.updated_at = utcnow()
    await db.commit()
    return await _build_hunt_response(db, session=session)


@router.post("/hunt/found", response_model=LandingHuntResponse)
async def mark_hunt_bug_found(
    payload: LandingHuntFoundRequest,
    db: AsyncSession = Depends(get_db),
):
    bug_key = normalize_bug_key(payload.bug_key)
    if not is_valid_bug_key(bug_key):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неизвестный интерактивный элемент",
        )

    session = await _find_or_create_session(
        db,
        session_token=normalize_session_token(payload.session_token),
    )
    current_found_keys = await _load_found_bug_keys(db, session.id)
    updated_found_keys, added, just_completed = apply_found_bug(current_found_keys, bug_key)

    if added:
        db.add(LandingHuntSessionItem(session_id=session.id, bug_key=bug_key))

    if just_completed and session.completed_at is None:
        session.completed_at = utcnow()
        await db.flush()
        await _ensure_session_promo_code(db, session)

    session.updated_at = utcnow()
    await db.commit()
    return await _build_hunt_response(db, session=session, just_completed=just_completed)
