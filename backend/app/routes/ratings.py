import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, distinct, desc, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_current_user_optional
from app.database import get_db
from app.models.contest import Submission
from app.models.user import UserProfile, UserRating
from app.schemas.ratings import (
    LeaderboardEntry,
    LeaderboardResponse,
    MyLeaderboardStatsBundleResponse,
    MyLeaderboardStatsResponse,
)

router = APIRouter(prefix="/ratings", tags=["Рейтинг"])
MY_STATS_CACHE_TTL_SECONDS = 30
_my_stats_cache: Dict[Tuple[int, str], Tuple[float, Dict[str, int]]] = {}
_my_stats_bundle_cache: Dict[int, Tuple[float, Dict[str, Dict[str, int]]]] = {}


def _read_cache_entry(timestamped_value: Optional[Tuple[float, Any]]) -> Optional[Any]:
    if not timestamped_value:
        return None
    saved_at, payload = timestamped_value
    if time.monotonic() - saved_at > MY_STATS_CACHE_TTL_SECONDS:
        return None
    return payload


def _read_cached_my_stats(user_id: int, kind: str) -> Optional[Dict[str, int]]:
    key = (user_id, kind)
    payload = _read_cache_entry(_my_stats_cache.get(key))
    if payload is None:
        _my_stats_cache.pop(key, None)
    return payload


def _read_cached_my_stats_bundle(user_id: int) -> Optional[Dict[str, Dict[str, int]]]:
    payload = _read_cache_entry(_my_stats_bundle_cache.get(user_id))
    if payload is None:
        _my_stats_bundle_cache.pop(user_id, None)
    return payload


def _write_my_stats_cache(user_id: int, bundle: Dict[str, Dict[str, int]]) -> None:
    now = time.monotonic()
    _my_stats_bundle_cache[user_id] = (now, bundle)
    contest = bundle.get("contest")
    practice = bundle.get("practice")
    if contest:
        _my_stats_cache[(user_id, "contest")] = (now, contest)
    if practice:
        _my_stats_cache[(user_id, "practice")] = (now, practice)


async def _load_my_stats_bundle_from_db(db: AsyncSession, user_id: int) -> Dict[str, Dict[str, int]]:
    # Быстрый расчёт ранга относительно текущего пользователя через count "пользователей выше"
    # вместо полного ROW_NUMBER() по всей таблице.
    rank_stmt = text(
        """
        WITH me AS (
            SELECT
                up.user_id,
                lower(up.username) AS username_key,
                ur.contest_rating,
                ur.practice_rating,
                ur.first_blood
            FROM user_profiles up
            JOIN user_ratings ur ON ur.user_id = up.user_id
            WHERE up.user_id = :user_id
        )
        SELECT
            me.contest_rating,
            me.practice_rating,
            me.first_blood,
            1 + (
                SELECT COUNT(*)
                FROM user_profiles up2
                JOIN user_ratings ur2 ON ur2.user_id = up2.user_id
                WHERE
                    ur2.contest_rating > me.contest_rating
                    OR (
                        ur2.contest_rating = me.contest_rating
                        AND (
                            ur2.first_blood > me.first_blood
                            OR (
                                ur2.first_blood = me.first_blood
                                AND (
                                    lower(up2.username) < me.username_key
                                    OR (
                                        lower(up2.username) = me.username_key
                                        AND up2.user_id < me.user_id
                                    )
                                )
                            )
                        )
                    )
            ) AS contest_rank,
            1 + (
                SELECT COUNT(*)
                FROM user_profiles up2
                JOIN user_ratings ur2 ON ur2.user_id = up2.user_id
                WHERE
                    ur2.practice_rating > me.practice_rating
                    OR (
                        ur2.practice_rating = me.practice_rating
                        AND (
                            ur2.first_blood > me.first_blood
                            OR (
                                ur2.first_blood = me.first_blood
                                AND (
                                    lower(up2.username) < me.username_key
                                    OR (
                                        lower(up2.username) = me.username_key
                                        AND up2.user_id < me.user_id
                                    )
                                )
                            )
                        )
                    )
            ) AS practice_rank
        FROM me
        """
    )

    row = (await db.execute(rank_stmt, {"user_id": user_id})).mappings().first()
    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден в рейтинге")

    first_blood = int(row.get("first_blood") or 0)
    return {
        "contest": {
            "rank": int(row["contest_rank"]),
            "rating": int(row.get("contest_rating") or 0),
            "first_blood": first_blood,
        },
        "practice": {
            "rank": int(row["practice_rank"]),
            "rating": int(row.get("practice_rating") or 0),
            "first_blood": first_blood,
        },
    }


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    kind: str = Query("contest", pattern="^(contest|practice)$"),
    current_user_data: Optional[tuple] = Depends(get_current_user_optional),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить рейтинг пользователей.

    kind:
      - contest: чемпионатный рейтинг
      - practice: практический рейтинг
    """
    user = current_user_data[0] if current_user_data else None

    if kind not in {"contest", "practice"}:
        raise HTTPException(status_code=400, detail="kind должен быть contest или practice")

    rating_col = UserRating.contest_rating if kind == "contest" else UserRating.practice_rating

    solved_query = (
        select(
            Submission.user_id,
            func.count(distinct(Submission.task_id)).label("solved")
        )
        .where(Submission.is_correct.is_(True))
    )

    if kind == "contest":
        solved_query = solved_query.where(Submission.contest_id.isnot(None))
    else:
        solved_query = solved_query.where(Submission.contest_id.is_(None))

    solved_subq = solved_query.group_by(Submission.user_id).subquery()

    result = await db.execute(
        select(
            UserProfile.user_id,
            UserProfile.username,
            UserProfile.avatar_url,
            rating_col.label("rating"),
            UserRating.first_blood,
            func.coalesce(solved_subq.c.solved, 0).label("solved"),
        )
        .join(UserRating, UserRating.user_id == UserProfile.user_id)
        .outerjoin(solved_subq, solved_subq.c.user_id == UserProfile.user_id)
        .order_by(desc(rating_col), desc(UserRating.first_blood), UserProfile.username.asc())
    )

    rows: List[tuple] = result.all()
    entries: List[LeaderboardEntry] = []

    for idx, row in enumerate(rows, start=1):
        entries.append(
            LeaderboardEntry(
                user_id=row.user_id,
                username=row.username,
                avatar_url=row.avatar_url,
                rating=row.rating or 0,
                solved=row.solved or 0,
                first_blood=row.first_blood or 0,
                rank=idx,
                is_current_user=user is not None and row.user_id == user.id,
            )
        )

    return LeaderboardResponse(
        kind=kind,
        generated_at=datetime.now(timezone.utc),
        entries=entries,
    )


@router.get("/my-stats", response_model=MyLeaderboardStatsResponse)
async def get_my_leaderboard_stats(
    kind: str = Query("contest", pattern="^(contest|practice)$"),
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Быстрый эндпоинт для главной страницы:
    возвращает только место и очки текущего пользователя без выгрузки полного лидерборда.
    """
    user, _profile = current_user_data

    if kind not in {"contest", "practice"}:
        raise HTTPException(status_code=400, detail="kind должен быть contest или practice")

    cached = _read_cached_my_stats(user.id, kind)
    if cached:
        return MyLeaderboardStatsResponse(
            kind=kind,
            rank=int(cached["rank"]),
            rating=int(cached["rating"]),
            first_blood=int(cached["first_blood"]),
        )

    bundle = _read_cached_my_stats_bundle(user.id)
    if bundle is None:
        bundle = await _load_my_stats_bundle_from_db(db, user.id)
        _write_my_stats_cache(user.id, bundle)
    snapshot = bundle.get(kind)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Пользователь не найден в рейтинге")

    return MyLeaderboardStatsResponse(
        kind=kind,
        rank=int(snapshot["rank"]),
        rating=int(snapshot["rating"]),
        first_blood=int(snapshot["first_blood"]),
    )


@router.get("/my-stats/both", response_model=MyLeaderboardStatsBundleResponse)
async def get_my_leaderboard_stats_bundle(
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Единый быстрый эндпоинт для главной:
    возвращает метрики текущего пользователя сразу для contest и practice.
    """
    user, _profile = current_user_data

    bundle = _read_cached_my_stats_bundle(user.id)
    if bundle is None:
        bundle = await _load_my_stats_bundle_from_db(db, user.id)
        _write_my_stats_cache(user.id, bundle)

    contest = bundle.get("contest")
    practice = bundle.get("practice")
    if not contest or not practice:
        raise HTTPException(status_code=404, detail="Пользователь не найден в рейтинге")

    return MyLeaderboardStatsBundleResponse(
        contest={
            "rank": int(contest["rank"]),
            "rating": int(contest["rating"]),
            "first_blood": int(contest["first_blood"]),
        },
        practice={
            "rank": int(practice["rank"]),
            "rating": int(practice["rating"]),
            "first_blood": int(practice["first_blood"]),
        },
    )
