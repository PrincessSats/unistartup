from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.contest import Contest, ContestTask, Task, Submission
from app.models.user import UserProfile
from app.schemas.contest import ContestSummary, FeaturedTask

router = APIRouter(prefix="/contests", tags=["Контесты"])


def _pick_knowledge_areas(tasks_data: List[tuple[Task, Optional[int]]]) -> List[str]:
    areas: List[str] = []
    for task, _points_override in tasks_data:
        if task.tags:
            for tag in task.tags:
                if tag and tag not in areas:
                    areas.append(tag)
        if task.category and task.category not in areas:
            areas.append(task.category)
    return areas[:4]


@router.get("/active", response_model=ContestSummary)
async def get_active_contest(
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user, _profile = current_user_data

    result = await db.execute(
        select(Contest)
        .where(Contest.start_at <= func.now(), Contest.end_at >= func.now())
        .order_by(Contest.start_at.desc())
        .limit(1)
    )
    contest = result.scalar_one_or_none()

    if contest is None:
        result = await db.execute(
            select(Contest).order_by(Contest.start_at.desc()).limit(1)
        )
        contest = result.scalar_one_or_none()

    if contest is None:
        raise HTTPException(status_code=404, detail="Контест не найден")

    tasks_result = await db.execute(
        select(Task, ContestTask.points_override)
        .join(ContestTask, ContestTask.task_id == Task.id)
        .where(ContestTask.contest_id == contest.id)
        .order_by(ContestTask.order_index.asc())
    )
    tasks_data = tasks_result.all()

    tasks_total = len(tasks_data)

    reward_points = 0
    for task, points_override in tasks_data:
        reward_points += points_override if points_override is not None else task.points

    solved_result = await db.execute(
        select(func.count(distinct(Submission.task_id))).where(
            Submission.contest_id == contest.id,
            Submission.user_id == user.id,
            Submission.is_correct.is_(True)
        )
    )
    tasks_solved = solved_result.scalar_one() or 0

    participants_result = await db.execute(
        select(func.count(distinct(Submission.user_id))).where(
            Submission.contest_id == contest.id
        )
    )
    participants_count = participants_result.scalar_one() or 0

    first_blood_result = await db.execute(
        select(UserProfile.username)
        .join(Submission, Submission.user_id == UserProfile.user_id)
        .where(
            Submission.contest_id == contest.id,
            Submission.is_correct.is_(True)
        )
        .order_by(Submission.submitted_at.asc())
        .limit(1)
    )
    first_blood_username = first_blood_result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    end_at = contest.end_at
    if end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=timezone.utc)
    days_left = max(0, (end_at.date() - now.date()).days)

    prev_result = await db.execute(
        select(Contest.id)
        .where(Contest.start_at < contest.start_at)
        .order_by(Contest.start_at.desc())
        .limit(1)
    )
    prev_contest_id = prev_result.scalar_one_or_none()

    next_result = await db.execute(
        select(Contest.id)
        .where(Contest.start_at > contest.start_at)
        .order_by(Contest.start_at.asc())
        .limit(1)
    )
    next_contest_id = next_result.scalar_one_or_none()

    knowledge_areas = _pick_knowledge_areas(tasks_data)

    featured_task = None
    if tasks_data:
        task, points_override = tasks_data[0]
        featured_task = FeaturedTask(
            id=task.id,
            title=task.title,
            description=task.participant_description or task.story,
            category=task.category,
            points=points_override if points_override is not None else task.points
        )

    return ContestSummary(
        id=contest.id,
        title=contest.title,
        description=contest.description,
        start_at=contest.start_at,
        end_at=contest.end_at,
        is_public=contest.is_public,
        leaderboard_visible=contest.leaderboard_visible,
        tasks_total=tasks_total,
        tasks_solved=tasks_solved,
        reward_points=reward_points,
        participants_count=participants_count,
        first_blood_username=first_blood_username,
        knowledge_areas=knowledge_areas,
        days_left=days_left,
        prev_contest_id=prev_contest_id,
        next_contest_id=next_contest_id,
        featured_task=featured_task
    )
