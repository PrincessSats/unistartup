from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.contest import Contest, ContestTask, Task, Submission, ContestParticipant, TaskFlag
from app.models.user import UserProfile
from app.security.rate_limit import RateLimit, enforce_rate_limit
from app.schemas.contest import (
    ContestSummary,
    FeaturedTask,
    ContestJoinResponse,
    ContestTaskInfo,
    ContestTaskState,
    ContestSubmissionRequest,
    ContestSubmissionResponse,
)

router = APIRouter(prefix="/contests", tags=["Контесты"])


def _pick_knowledge_areas(tasks_data: List[tuple[Task, ContestTask]]) -> List[str]:
    areas: List[str] = []
    for task, _contest_task in tasks_data:
        if task.tags:
            for tag in task.tags:
                if tag and tag not in areas:
                    areas.append(tag)
        if task.category and task.category not in areas:
            areas.append(task.category)
    return areas[:4]


def _merge_task(task: Task, contest_task: ContestTask) -> ContestTaskInfo:
    return ContestTaskInfo(
        id=task.id,
        title=contest_task.override_title or task.title,
        category=contest_task.override_category or task.category,
        difficulty=contest_task.override_difficulty or task.difficulty,
        points=contest_task.points_override if contest_task.points_override is not None else task.points,
        tags=contest_task.override_tags if contest_task.override_tags is not None else (task.tags or []),
        participant_description=contest_task.override_participant_description or task.participant_description or task.story,
        order_index=contest_task.order_index,
        is_solved=False,
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@router.get("/active", response_model=ContestSummary)
async def get_active_contest(
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    user, profile = current_user_data
    is_admin = profile.role == "admin"

    active_query = (
        select(Contest)
        .where(Contest.start_at <= func.now(), Contest.end_at >= func.now())
        .order_by(Contest.start_at.desc())
        .limit(1)
    )
    if not is_admin:
        active_query = active_query.where(Contest.is_public.is_(True))

    result = await db.execute(active_query)
    contest = result.scalar_one_or_none()

    if contest is None:
        latest_query = select(Contest).order_by(Contest.start_at.desc()).limit(1)
        if not is_admin:
            latest_query = latest_query.where(Contest.is_public.is_(True))
        result = await db.execute(latest_query)
        contest = result.scalar_one_or_none()

    if contest is None:
        raise HTTPException(status_code=404, detail="Контест не найден")

    tasks_result = await db.execute(
        select(Task, ContestTask)
        .join(ContestTask, ContestTask.task_id == Task.id)
        .where(ContestTask.contest_id == contest.id)
        .order_by(ContestTask.order_index.asc())
    )
    tasks_data = tasks_result.all()

    tasks_total = len(tasks_data)

    reward_points = 0
    for task, contest_task in tasks_data:
        reward_points += contest_task.points_override if contest_task.points_override is not None else task.points

    solved_result = await db.execute(
        select(func.count(distinct(Submission.task_id))).where(
            Submission.contest_id == contest.id,
            Submission.user_id == user.id,
            Submission.is_correct.is_(True)
        )
    )
    tasks_solved = solved_result.scalar_one() or 0

    participants_result = await db.execute(
        select(func.count(ContestParticipant.user_id)).where(
            ContestParticipant.contest_id == contest.id
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
        task, contest_task = tasks_data[0]
        featured_task = FeaturedTask(
            id=task.id,
            title=contest_task.override_title or task.title,
            description=contest_task.override_participant_description or task.participant_description or task.story,
            category=contest_task.override_category or task.category,
            points=contest_task.points_override if contest_task.points_override is not None else task.points
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


@router.post("/{contest_id}/join", response_model=ContestJoinResponse)
async def join_contest(
    contest_id: int,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, profile = current_user_data

    contest = (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none()
    if contest is None:
        raise HTTPException(status_code=404, detail="Контест не найден")
    if not contest.is_public and profile.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Контест недоступен")

    existing = (
        await db.execute(
            select(ContestParticipant).where(
                ContestParticipant.contest_id == contest_id,
                ContestParticipant.user_id == user.id,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        participant = ContestParticipant(
            contest_id=contest_id,
            user_id=user.id,
            last_active_at=datetime.now(timezone.utc),
        )
        db.add(participant)
        await db.commit()
        await db.refresh(participant)
        return ContestJoinResponse(contest_id=contest_id, joined_at=participant.joined_at, is_joined=True)

    existing.last_active_at = datetime.now(timezone.utc)
    await db.commit()
    return ContestJoinResponse(contest_id=contest_id, joined_at=existing.joined_at, is_joined=True)


@router.get("/{contest_id}/current-task", response_model=ContestTaskState)
async def get_current_task(
    contest_id: int,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, profile = current_user_data

    contest = (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none()
    if contest is None:
        raise HTTPException(status_code=404, detail="Контест не найден")
    if not contest.is_public and profile.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Контест недоступен")

    now = datetime.now(timezone.utc)
    if _ensure_utc(contest.start_at) > now or _ensure_utc(contest.end_at) < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Контест не активен")

    participant = (
        await db.execute(
            select(ContestParticipant).where(
                ContestParticipant.contest_id == contest_id,
                ContestParticipant.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if participant is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нужно вступить в контест")

    tasks_result = await db.execute(
        select(ContestTask, Task)
        .join(Task, Task.id == ContestTask.task_id)
        .where(ContestTask.contest_id == contest_id)
        .order_by(ContestTask.order_index.asc())
    )
    tasks_rows = tasks_result.all()
    tasks_total = len(tasks_rows)
    if tasks_total == 0:
        return ContestTaskState(
            contest_id=contest_id,
            task=None,
            progress_index=0,
            tasks_total=0,
            solved_task_ids=[],
            previous_tasks=[],
            finished=True,
        )

    solved_result = await db.execute(
        select(distinct(Submission.task_id)).where(
            Submission.contest_id == contest_id,
            Submission.user_id == user.id,
            Submission.is_correct.is_(True),
        )
    )
    solved_task_ids = [row[0] for row in solved_result.all()]

    merged_tasks = []
    for contest_task, task in tasks_rows:
        merged_tasks.append(_merge_task(task, contest_task))

    current_task = None
    for task in merged_tasks:
        task.is_solved = task.id in solved_task_ids
        if current_task is None and not task.is_solved:
            current_task = task

    previous_tasks = [task for task in merged_tasks if task.is_solved]
    finished = current_task is None and tasks_total > 0

    participant.last_active_at = datetime.now(timezone.utc)
    if finished and participant.completed_at is None:
        participant.completed_at = datetime.now(timezone.utc)
    await db.commit()

    progress_index = len(previous_tasks) + (0 if finished else 1)

    return ContestTaskState(
        contest_id=contest_id,
        task=current_task,
        progress_index=progress_index,
        tasks_total=tasks_total,
        solved_task_ids=solved_task_ids,
        previous_tasks=previous_tasks,
        finished=finished,
    )


@router.post("/{contest_id}/submit", response_model=ContestSubmissionResponse)
async def submit_flag(
    request: Request,
    contest_id: int,
    payload: ContestSubmissionRequest,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, profile = current_user_data
    enforce_rate_limit(
        request,
        scope="contest_submit_flag",
        subject=f"{user.id}:{contest_id}",
        rule=RateLimit(max_requests=30, window_seconds=60),
    )

    contest = (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none()
    if contest is None:
        raise HTTPException(status_code=404, detail="Контест не найден")
    if not contest.is_public and profile.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Контест недоступен")

    now = datetime.now(timezone.utc)
    if _ensure_utc(contest.start_at) > now or _ensure_utc(contest.end_at) < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Контест не активен")

    participant = (
        await db.execute(
            select(ContestParticipant).where(
                ContestParticipant.contest_id == contest_id,
                ContestParticipant.user_id == user.id,
            )
        )
    ).scalar_one_or_none()
    if participant is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нужно вступить в контест")

    tasks_result = await db.execute(
        select(ContestTask, Task)
        .join(Task, Task.id == ContestTask.task_id)
        .where(ContestTask.contest_id == contest_id)
        .order_by(ContestTask.order_index.asc())
    )
    tasks_rows = tasks_result.all()
    if not tasks_rows:
        raise HTTPException(status_code=400, detail="В контесте нет задач")

    solved_result = await db.execute(
        select(distinct(Submission.task_id)).where(
            Submission.contest_id == contest_id,
            Submission.user_id == user.id,
            Submission.is_correct.is_(True),
        )
    )
    solved_task_ids = [row[0] for row in solved_result.all()]

    merged_tasks = []
    for contest_task, task in tasks_rows:
        merged_tasks.append((_merge_task(task, contest_task), contest_task, task))

    current_task = None
    for task_info, contest_task, task in merged_tasks:
        if task_info.id not in solved_task_ids:
            current_task = (task_info, contest_task, task)
            break

    if current_task is None:
        return ContestSubmissionResponse(is_correct=False, awarded_points=0, next_task=None, finished=True)

    if payload.task_id is not None and payload.task_id != current_task[0].id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Можно сдавать только текущую задачу")

    task_info, contest_task, task = current_task

    submitted_value = (payload.flag or "").strip()
    if not submitted_value:
        raise HTTPException(status_code=400, detail="Флаг пустой")

    flags_result = await db.execute(
        select(TaskFlag).where(TaskFlag.task_id == task.id)
    )
    flags = flags_result.scalars().all()

    matched_flag = None
    for flag in flags:
        if flag.expected_value and flag.expected_value == submitted_value:
            matched_flag = flag
            break

    is_correct = matched_flag is not None
    already_solved = task.id in solved_task_ids
    awarded_points = 0
    if is_correct and not already_solved:
        awarded_points = contest_task.points_override if contest_task.points_override is not None else task.points

    submission = Submission(
        contest_id=contest_id,
        task_id=task.id,
        user_id=user.id,
        flag_id=matched_flag.flag_id if matched_flag else "unknown",
        submitted_value=submitted_value,
        is_correct=is_correct,
        awarded_points=awarded_points,
    )
    db.add(submission)

    participant.last_active_at = datetime.now(timezone.utc)

    if is_correct and not already_solved:
        solved_task_ids.append(task.id)

    next_task = None
    finished = False
    for task_info, contest_task, task in merged_tasks:
        if task_info.id not in solved_task_ids:
            if task_info.id != task.id or (task_info.id == task.id and not is_correct):
                next_task = task_info
            break
    else:
        finished = True
        if participant.completed_at is None:
            participant.completed_at = datetime.now(timezone.utc)

    await db.commit()

    return ContestSubmissionResponse(
        is_correct=is_correct,
        awarded_points=awarded_points,
        next_task=next_task if is_correct else None,
        finished=finished,
    )
