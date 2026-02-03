from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, distinct, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.models.contest import Submission
from app.models.user import UserProfile, UserRating
from app.schemas.ratings import LeaderboardEntry, LeaderboardResponse

router = APIRouter(prefix="/ratings", tags=["Рейтинг"])


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def get_leaderboard(
    kind: str = Query("contest", pattern="^(contest|practice)$"),
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Получить рейтинг пользователей.

    kind:
      - contest: чемпионатный рейтинг
      - practice: практический рейтинг
    """
    user, _profile = current_user_data

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
                is_current_user=row.user_id == user.id,
            )
        )

    return LeaderboardResponse(
        kind=kind,
        generated_at=datetime.now(timezone.utc),
        entries=entries,
    )
