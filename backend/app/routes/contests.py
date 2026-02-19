from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select, func
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


def _is_task_completed(
    task_id: int,
    required_flag_ids: List[str],
    solved_flag_ids: Set[str],
    legacy_solved_task_ids: Set[int],
) -> bool:
    if required_flag_ids:
        return set(required_flag_ids).issubset(solved_flag_ids)
    return task_id in legacy_solved_task_ids


def _merge_task(
    task: Task,
    contest_task: ContestTask,
    task_flags: Optional[List[TaskFlag]] = None,
    solved_flag_ids: Optional[Set[str]] = None,
) -> ContestTaskInfo:
    task_flags = task_flags or []
    solved_flag_ids = solved_flag_ids or set()
    required_flags = [
        ContestTaskInfo.FlagInfo(
            flag_id=flag.flag_id,
            format=flag.format,
            description=flag.description,
            is_solved=flag.flag_id in solved_flag_ids,
        )
        for flag in task_flags
    ]

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
        required_flags=required_flags,
        required_flags_count=len(required_flags),
        solved_flags_count=sum(1 for flag in required_flags if flag.is_solved),
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


async def _load_task_flags(
    db: AsyncSession,
    task_ids: List[int],
) -> Dict[int, List[TaskFlag]]:
    if not task_ids:
        return {}

    flags_result = await db.execute(
        select(TaskFlag)
        .where(TaskFlag.task_id.in_(task_ids))
        .order_by(TaskFlag.task_id.asc(), TaskFlag.id.asc())
    )
    flags_by_task: Dict[int, List[TaskFlag]] = {}
    for flag in flags_result.scalars().all():
        flags_by_task.setdefault(flag.task_id, []).append(flag)
    return flags_by_task


async def _load_user_correct_progress(
    db: AsyncSession,
    contest_id: int,
    user_id: int,
    task_ids: List[int],
) -> Tuple[Dict[int, Set[str]], Set[int]]:
    if not task_ids:
        return {}, set()

    solved_rows = await db.execute(
        select(Submission.task_id, Submission.flag_id).where(
            Submission.contest_id == contest_id,
            Submission.user_id == user_id,
            Submission.task_id.in_(task_ids),
            Submission.is_correct.is_(True),
        )
    )

    solved_flags_by_task: Dict[int, Set[str]] = {}
    legacy_solved_task_ids: Set[int] = set()
    for task_id, flag_id in solved_rows.all():
        legacy_solved_task_ids.add(task_id)
        if flag_id:
            solved_flags_by_task.setdefault(task_id, set()).add(flag_id)
    return solved_flags_by_task, legacy_solved_task_ids


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

    task_ids = [task.id for task, _contest_task in tasks_data]
    flags_by_task = await _load_task_flags(db, task_ids)
    solved_flags_by_task, legacy_solved_task_ids = await _load_user_correct_progress(
        db,
        contest.id,
        user.id,
        task_ids,
    )
    tasks_solved = 0
    for task, _contest_task in tasks_data:
        required_flag_ids = [flag.flag_id for flag in flags_by_task.get(task.id, [])]
        if _is_task_completed(
            task.id,
            required_flag_ids,
            solved_flags_by_task.get(task.id, set()),
            legacy_solved_task_ids,
        ):
            tasks_solved += 1

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

    task_ids = [task.id for _contest_task, task in tasks_rows]
    flags_by_task = await _load_task_flags(db, task_ids)
    solved_flags_by_task, legacy_solved_task_ids = await _load_user_correct_progress(
        db,
        contest_id,
        user.id,
        task_ids,
    )

    merged_tasks: List[ContestTaskInfo] = []
    solved_task_ids: List[int] = []
    current_task = None
    for contest_task, task in tasks_rows:
        required_flags = flags_by_task.get(task.id, [])
        solved_flag_ids = solved_flags_by_task.get(task.id, set())
        task_info = _merge_task(task, contest_task, required_flags, solved_flag_ids)
        required_flag_ids = [flag.flag_id for flag in required_flags]
        task_info.is_solved = _is_task_completed(
            task.id,
            required_flag_ids,
            solved_flag_ids,
            legacy_solved_task_ids,
        )
        if task_info.is_solved:
            solved_task_ids.append(task_info.id)
        elif current_task is None:
            current_task = task_info
        merged_tasks.append(task_info)

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

    task_ids = [task.id for _contest_task, task in tasks_rows]
    flags_by_task = await _load_task_flags(db, task_ids)
    solved_flags_by_task, legacy_solved_task_ids = await _load_user_correct_progress(
        db,
        contest_id,
        user.id,
        task_ids,
    )

    merged_tasks: List[tuple[ContestTaskInfo, ContestTask, Task]] = []
    current_task = None
    for contest_task, task in tasks_rows:
        required_flags = flags_by_task.get(task.id, [])
        solved_flag_ids = solved_flags_by_task.get(task.id, set())
        task_info = _merge_task(task, contest_task, required_flags, solved_flag_ids)
        required_flag_ids = [flag.flag_id for flag in required_flags]
        task_info.is_solved = _is_task_completed(
            task.id,
            required_flag_ids,
            solved_flag_ids,
            legacy_solved_task_ids,
        )
        merged_tasks.append((task_info, contest_task, task))
        if current_task is None and not task_info.is_solved:
            current_task = (task_info, contest_task, task)

    if current_task is None:
        return ContestSubmissionResponse(is_correct=False, awarded_points=0, next_task=None, finished=True)

    if payload.task_id is not None and payload.task_id != current_task[0].id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Можно сдавать только текущую задачу")

    task_info, contest_task, task = current_task

    submitted_value = (payload.flag or "").strip()
    if not submitted_value:
        raise HTTPException(status_code=400, detail="Флаг пустой")

    flags = flags_by_task.get(task.id, [])
    if not flags:
        raise HTTPException(status_code=400, detail="У задачи не настроены флаги")

    matched_flag = None
    target_flag_id = (payload.flag_id or "").strip()
    if target_flag_id:
        for flag in flags:
            if flag.flag_id == target_flag_id:
                matched_flag = flag if flag.expected_value and flag.expected_value == submitted_value else None
                break
        else:
            raise HTTPException(status_code=400, detail="Неизвестный flag_id для текущей задачи")
    else:
        for flag in flags:
            if flag.expected_value and flag.expected_value == submitted_value:
                matched_flag = flag
                break

    is_correct = matched_flag is not None
    solved_flag_ids = set(solved_flags_by_task.get(task.id, set()))
    was_task_completed = task_info.is_solved
    if is_correct:
        solved_flag_ids.add(matched_flag.flag_id)
        solved_flags_by_task[task.id] = solved_flag_ids
        legacy_solved_task_ids.add(task.id)

    required_flag_ids = [flag.flag_id for flag in flags]
    is_task_completed_now = _is_task_completed(
        task.id,
        required_flag_ids,
        solved_flag_ids,
        legacy_solved_task_ids,
    )

    awarded_points = 0
    if is_correct and not was_task_completed and is_task_completed_now:
        awarded_points = contest_task.points_override if contest_task.points_override is not None else task.points

    submission = Submission(
        contest_id=contest_id,
        task_id=task.id,
        user_id=user.id,
        flag_id=matched_flag.flag_id if matched_flag else (target_flag_id or "unknown"),
        submitted_value=submitted_value,
        is_correct=is_correct,
        awarded_points=awarded_points,
    )
    db.add(submission)

    participant.last_active_at = datetime.now(timezone.utc)

    next_task = None
    finished = True
    for _candidate_info, candidate_contest_task, candidate_task in merged_tasks:
        candidate_required_flags = flags_by_task.get(candidate_task.id, [])
        candidate_solved_flag_ids = solved_flags_by_task.get(candidate_task.id, set())
        candidate_required_flag_ids = [flag.flag_id for flag in candidate_required_flags]
        candidate_is_solved = _is_task_completed(
            candidate_task.id,
            candidate_required_flag_ids,
            candidate_solved_flag_ids,
            legacy_solved_task_ids,
        )
        if not candidate_is_solved:
            finished = False
            if (
                is_correct
                and is_task_completed_now
                and candidate_task.id != task.id
            ):
                next_task = _merge_task(
                    candidate_task,
                    candidate_contest_task,
                    candidate_required_flags,
                    candidate_solved_flag_ids,
                )
            break

    if finished and participant.completed_at is None:
        participant.completed_at = datetime.now(timezone.utc)

    await db.commit()

    return ContestSubmissionResponse(
        is_correct=is_correct,
        awarded_points=awarded_points,
        next_task=next_task if is_correct else None,
        finished=finished,
    )
