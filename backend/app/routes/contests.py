from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.auth.dependencies import get_current_user
from app.models.contest import Contest, ContestTask, Task, Submission, ContestParticipant, TaskFlag, ContestTaskRating
from app.models.user import UserProfile
from app.security.rate_limit import RateLimit, enforce_rate_limit
from app.services.chat_task import (
    abort_active_chat_session,
    ChatTaskError,
    ChatTaskSessionExpiredError,
    ChatTaskSessionReadOnlyError,
    cleanup_expired_unsolved_chat_sessions,
    derive_dynamic_flag_token_candidates,
    extract_flag_token_content,
    generate_chat_reply,
    get_chat_limits_for_task,
    get_or_create_chat_session,
    get_session_for_chat_submit,
    list_chat_messages,
    mark_chat_session_solved,
    normalize_flag_token_content,
)
from app.schemas.contest import (
    ContestSummary,
    FeaturedTask,
    ContestJoinResponse,
    ContestLeaderboardResponse,
    ContestLeaderboardRow,
    ContestMyResultItem,
    ContestMyResultsResponse,
    ContestTaskInfo,
    ContestTaskState,
    ContestSubmissionRequest,
    ContestSubmissionResponse,
    ContestTaskChatSession,
    ContestTaskChatSessionResponse,
    ContestTaskChatMessageRequest,
    ContestTaskChatMessageResponse,
    ContestTaskChatMessage,
    TaskChatLimits,
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

    chat_limits = None
    if (task.access_type or "").strip().lower() == "chat":
        limits = get_chat_limits_for_task(task)
        chat_limits = TaskChatLimits(
            user_message_max_chars=limits.user_message_max_chars,
            model_max_output_tokens=limits.model_max_output_tokens,
            session_ttl_minutes=limits.session_ttl_minutes,
        )

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
        access_type=task.access_type or "just_flag",
        chat_limits=chat_limits,
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


def _ensure_contest_access(contest: Optional[Contest], role: str) -> Contest:
    if contest is None:
        raise HTTPException(status_code=404, detail="Контест не найден")
    if not contest.is_public and role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Контест недоступен")
    return contest


def _ensure_contest_is_active(contest: Contest) -> None:
    now = datetime.now(timezone.utc)
    if _ensure_utc(contest.start_at) > now or _ensure_utc(contest.end_at) < now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Контест не активен")


async def _ensure_contest_participant(
    db: AsyncSession,
    *,
    contest_id: int,
    user_id: int,
) -> ContestParticipant:
    participant = (
        await db.execute(
            select(ContestParticipant).where(
                ContestParticipant.contest_id == contest_id,
                ContestParticipant.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if participant is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Нужно вступить в контест")
    return participant


async def _build_contest_progress_context(
    db: AsyncSession,
    *,
    contest_id: int,
    user_id: int,
) -> tuple[
    List[tuple[ContestTaskInfo, ContestTask, Task]],
    Optional[tuple[ContestTaskInfo, ContestTask, Task]],
    Dict[int, List[TaskFlag]],
    Dict[int, Set[str]],
    Set[int],
]:
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
        user_id,
        task_ids,
    )

    merged_tasks: List[tuple[ContestTaskInfo, ContestTask, Task]] = []
    current_task: Optional[tuple[ContestTaskInfo, ContestTask, Task]] = None
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

    return (
        merged_tasks,
        current_task,
        flags_by_task,
        solved_flags_by_task,
        legacy_solved_task_ids,
    )


def _build_chat_session_payload(
    *,
    session_id: int,
    status_value: str,
    read_only: bool,
    expires_at: datetime,
    limits: TaskChatLimits,
    messages: List[ContestTaskChatMessage],
) -> ContestTaskChatSession:
    return ContestTaskChatSession(
        session_id=session_id,
        status=status_value,
        read_only=read_only,
        expires_at=_ensure_utc(expires_at),
        limits=limits,
        messages=messages,
    )


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


@router.get(
    "/{contest_id}/tasks/{task_id}/chat/session",
    response_model=ContestTaskChatSessionResponse,
)
async def get_contest_task_chat_session(
    contest_id: int,
    task_id: int,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, profile = current_user_data

    contest = _ensure_contest_access(
        (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none(),
        profile.role,
    )
    _ensure_contest_is_active(contest)
    participant = await _ensure_contest_participant(db, contest_id=contest_id, user_id=user.id)

    _merged_tasks, current_task, _flags_by_task, _solved_flags_by_task, _legacy_solved_task_ids = (
        await _build_contest_progress_context(db, contest_id=contest_id, user_id=user.id)
    )
    if current_task is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Контест завершён")
    _task_info, _contest_task, task = current_task
    if task.id != task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Чат доступен только для текущей задачи",
        )
    if (task.access_type or "").strip().lower() != "chat":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У текущей задачи не настроен чат",
        )

    session, read_only = await get_or_create_chat_session(
        db,
        task=task,
        user_id=user.id,
        contest_id=contest_id,
    )
    session_messages = await list_chat_messages(db, session_id=session.id)
    limits = get_chat_limits_for_task(task)
    payload_messages = [
        ContestTaskChatMessage(
            role=item.role,
            content=item.content,
            created_at=_ensure_utc(item.created_at),
        )
        for item in session_messages
    ]
    participant.last_active_at = datetime.now(timezone.utc)
    await db.commit()

    return ContestTaskChatSessionResponse(
        contest_id=contest_id,
        task_id=task_id,
        session=_build_chat_session_payload(
            session_id=session.id,
            status_value=session.status,
            read_only=read_only,
            expires_at=session.expires_at,
            limits=TaskChatLimits(
                user_message_max_chars=limits.user_message_max_chars,
                model_max_output_tokens=limits.model_max_output_tokens,
                session_ttl_minutes=limits.session_ttl_minutes,
            ),
            messages=payload_messages,
        ),
    )


@router.post(
    "/{contest_id}/tasks/{task_id}/chat/messages",
    response_model=ContestTaskChatMessageResponse,
)
async def send_contest_task_chat_message(
    request: Request,
    contest_id: int,
    task_id: int,
    payload: ContestTaskChatMessageRequest,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, profile = current_user_data
    enforce_rate_limit(
        request,
        scope="contest_task_chat_message",
        subject=f"{user.id}:{contest_id}:{task_id}",
        rule=RateLimit(max_requests=30, window_seconds=60),
    )

    contest = _ensure_contest_access(
        (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none(),
        profile.role,
    )
    _ensure_contest_is_active(contest)
    participant = await _ensure_contest_participant(db, contest_id=contest_id, user_id=user.id)

    _merged_tasks, current_task, _flags_by_task, _solved_flags_by_task, _legacy_solved_task_ids = (
        await _build_contest_progress_context(db, contest_id=contest_id, user_id=user.id)
    )
    if current_task is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Контест завершён")
    _task_info, _contest_task, task = current_task
    if task.id != task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Чат доступен только для текущей задачи",
        )
    if (task.access_type or "").strip().lower() != "chat":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У текущей задачи не настроен чат",
        )

    session, read_only = await get_or_create_chat_session(
        db,
        task=task,
        user_id=user.id,
        contest_id=contest_id,
    )
    if read_only:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Сессия уже завершена после успешной сдачи флага",
        )

    try:
        assistant_message = await generate_chat_reply(
            db,
            task=task,
            session=session,
            user_message=payload.message,
        )
    except ChatTaskSessionReadOnlyError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ChatTaskSessionExpiredError as exc:
        await cleanup_expired_unsolved_chat_sessions(
            db,
            task_id=task.id,
            user_id=user.id,
            contest_id=contest_id,
        )
        await db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except ChatTaskError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    session_messages = await list_chat_messages(db, session_id=session.id)
    limits = get_chat_limits_for_task(task)
    payload_messages = [
        ContestTaskChatMessage(
            role=item.role,
            content=item.content,
            created_at=_ensure_utc(item.created_at),
        )
        for item in session_messages
    ]
    participant.last_active_at = datetime.now(timezone.utc)
    await db.commit()

    return ContestTaskChatMessageResponse(
        contest_id=contest_id,
        task_id=task_id,
        assistant_message=assistant_message,
        session=_build_chat_session_payload(
            session_id=session.id,
            status_value=session.status,
            read_only=False,
            expires_at=session.expires_at,
            limits=TaskChatLimits(
                user_message_max_chars=limits.user_message_max_chars,
                model_max_output_tokens=limits.model_max_output_tokens,
                session_ttl_minutes=limits.session_ttl_minutes,
            ),
            messages=payload_messages,
        ),
    )


@router.delete(
    "/{contest_id}/tasks/{task_id}/chat/session",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def abort_contest_task_chat_session(
    contest_id: int,
    task_id: int,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, profile = current_user_data

    contest = _ensure_contest_access(
        (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none(),
        profile.role,
    )
    _ensure_contest_is_active(contest)
    participant = await _ensure_contest_participant(db, contest_id=contest_id, user_id=user.id)

    _merged_tasks, current_task, _flags_by_task, _solved_flags_by_task, _legacy_solved_task_ids = (
        await _build_contest_progress_context(db, contest_id=contest_id, user_id=user.id)
    )
    if current_task is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Контест завершён")
    _task_info, _contest_task, task = current_task
    if task.id != task_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Чат доступен только для текущей задачи",
        )
    if (task.access_type or "").strip().lower() != "chat":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="У текущей задачи не настроен чат",
        )

    session = await get_session_for_chat_submit(
        db,
        task_id=task.id,
        user_id=user.id,
        contest_id=contest_id,
        include_solved=True,
    )
    if session is not None and session.status == "solved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="После сдачи флага в чемпионате чат нельзя перезапускать",
        )

    await abort_active_chat_session(
        db,
        task_id=task.id,
        user_id=user.id,
        contest_id=contest_id,
    )
    participant.last_active_at = datetime.now(timezone.utc)
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{contest_id}/leaderboard", response_model=ContestLeaderboardResponse)
async def get_contest_leaderboard(
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

    participants_result = await db.execute(
        select(ContestParticipant.user_id, UserProfile.username, UserProfile.avatar_url)
        .outerjoin(UserProfile, UserProfile.user_id == ContestParticipant.user_id)
        .where(ContestParticipant.contest_id == contest_id)
        .order_by(ContestParticipant.joined_at.asc())
    )
    participant_rows = participants_result.all()
    if not participant_rows:
        return ContestLeaderboardResponse(contest_id=contest_id, total_participants=0, rows=[], me=None)

    submissions_result = await db.execute(
        select(
            Submission.user_id,
            Submission.task_id,
            Submission.flag_id,
            Submission.awarded_points,
            Submission.submitted_at,
            Submission.id,
        )
        .where(
            Submission.contest_id == contest_id,
            Submission.is_correct.is_(True),
        )
        .order_by(Submission.submitted_at.asc(), Submission.id.asc())
    )
    submission_rows = submissions_result.all()

    points_by_user: Dict[int, int] = defaultdict(int)
    flags_by_user: Dict[int, Set[Tuple[int, str]]] = defaultdict(set)
    last_submission_by_user: Dict[int, datetime] = {}
    first_blood_winner_by_task: Dict[int, int] = {}

    for row in submission_rows:
        points_by_user[row.user_id] += int(row.awarded_points or 0)
        stable_flag_id = row.flag_id or f"submission:{row.id}"
        flags_by_user[row.user_id].add((row.task_id, stable_flag_id))

        submitted_at = _ensure_utc(row.submitted_at)
        previous_last = last_submission_by_user.get(row.user_id)
        if previous_last is None or submitted_at > previous_last:
            last_submission_by_user[row.user_id] = submitted_at

        if (row.awarded_points or 0) > 0 and row.task_id not in first_blood_winner_by_task:
            first_blood_winner_by_task[row.task_id] = row.user_id

    first_blood_count_by_user: Dict[int, int] = defaultdict(int)
    for winner_user_id in first_blood_winner_by_task.values():
        first_blood_count_by_user[winner_user_id] += 1

    leaderboard_rows: List[ContestLeaderboardRow] = []
    for participant_user_id, participant_username, participant_avatar_url in participant_rows:
        leaderboard_rows.append(
            ContestLeaderboardRow(
                rank=0,
                user_id=participant_user_id,
                username=participant_username or f"user_{participant_user_id}",
                avatar_url=participant_avatar_url,
                points=points_by_user.get(participant_user_id, 0),
                flags_collected=len(flags_by_user.get(participant_user_id, set())),
                first_blood_count=first_blood_count_by_user.get(participant_user_id, 0),
                last_submission_at=last_submission_by_user.get(participant_user_id),
                is_me=participant_user_id == user.id,
            )
        )

    far_future = datetime.max.replace(tzinfo=timezone.utc)
    leaderboard_rows.sort(
        key=lambda row: (
            -row.points,
            row.last_submission_at or far_future,
            -row.first_blood_count,
            row.username.lower(),
            row.user_id,
        )
    )

    me_row = None
    for index, row in enumerate(leaderboard_rows, start=1):
        row.rank = index
        if row.is_me:
            me_row = row

    return ContestLeaderboardResponse(
        contest_id=contest_id,
        total_participants=len(leaderboard_rows),
        rows=leaderboard_rows,
        me=me_row,
    )


@router.get("/{contest_id}/my-results", response_model=ContestMyResultsResponse)
async def get_contest_my_results(
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

    result = await db.execute(
        select(
            Submission.id,
            Submission.task_id,
            Submission.flag_id,
            Submission.submitted_value,
            Submission.awarded_points,
            Submission.submitted_at,
            Task.title,
            ContestTask.override_title,
        )
        .join(Task, Task.id == Submission.task_id)
        .outerjoin(
            ContestTask,
            and_(
                ContestTask.contest_id == contest_id,
                ContestTask.task_id == Submission.task_id,
            ),
        )
        .where(
            Submission.contest_id == contest_id,
            Submission.user_id == user.id,
            Submission.is_correct.is_(True),
        )
        .order_by(Submission.submitted_at.asc(), Submission.id.asc())
    )
    rows = result.all()

    seen_keys: Set[Tuple[int, str]] = set()
    items: List[ContestMyResultItem] = []
    total_points = 0

    for row in rows:
        stable_flag_id = row.flag_id or f"submission:{row.id}"
        dedupe_key = (row.task_id, stable_flag_id)
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        points = int(row.awarded_points or 0)
        total_points += points
        items.append(
            ContestMyResultItem(
                task_id=row.task_id,
                task_title=row.override_title or row.title or f"Task {row.task_id}",
                flag=row.submitted_value or stable_flag_id,
                points=points,
                submitted_at=_ensure_utc(row.submitted_at),
            )
        )

    return ContestMyResultsResponse(
        contest_id=contest_id,
        user_id=user.id,
        items=items,
        total_points=total_points,
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

    contest = _ensure_contest_access(
        (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none(),
        profile.role,
    )
    _ensure_contest_is_active(contest)
    participant = await _ensure_contest_participant(db, contest_id=contest_id, user_id=user.id)

    (
        merged_tasks,
        current_task,
        flags_by_task,
        solved_flags_by_task,
        legacy_solved_task_ids,
    ) = await _build_contest_progress_context(
        db,
        contest_id=contest_id,
        user_id=user.id,
    )

    if current_task is None:
        return ContestSubmissionResponse(is_correct=False, awarded_points=0, next_task=None, finished=True)

    if payload.task_id is not None and payload.task_id != current_task[0].id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Можно сдавать только текущую задачу")

    task_info, contest_task, task = current_task

    submitted_value = (payload.flag or "").strip()
    if not submitted_value:
        raise HTTPException(status_code=400, detail="Флаг пустой")

    flags = flags_by_task.get(task.id, [])
    target_flag_id = (payload.flag_id or "").strip()
    matched_flag: Optional[TaskFlag] = None
    resolved_flag_id = target_flag_id or (flags[0].flag_id if flags else "main")

    is_chat_task = (task.access_type or "").strip().lower() == "chat"
    if is_chat_task:
        if target_flag_id and flags and not any(flag.flag_id == target_flag_id for flag in flags):
            raise HTTPException(status_code=400, detail="Неизвестный flag_id для текущей задачи")

        session = await get_session_for_chat_submit(
            db,
            task_id=task.id,
            user_id=user.id,
            contest_id=contest_id,
            include_solved=False,
        )
        if session is None:
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Чат-сессия истекла или не создана. Откройте чат задачи.",
            )
        try:
            expected_tokens = derive_dynamic_flag_token_candidates(session.flag_seed)
        except ChatTaskError as exc:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

        submitted_token = normalize_flag_token_content(extract_flag_token_content(submitted_value))
        is_correct = bool(submitted_token) and submitted_token in expected_tokens
        if is_correct and session.status == "active":
            mark_chat_session_solved(session)
    else:
        if not flags:
            raise HTTPException(status_code=400, detail="У задачи не настроены флаги")
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
        if is_correct and matched_flag is not None:
            resolved_flag_id = matched_flag.flag_id
    solved_flag_ids = set(solved_flags_by_task.get(task.id, set()))
    was_task_completed = task_info.is_solved
    if is_correct:
        solved_flag_ids.add(resolved_flag_id)
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
        flag_id=resolved_flag_id if is_correct else (target_flag_id or resolved_flag_id or "unknown"),
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


class TaskRatingRequest(BaseModel):
    rating: int = Field(..., ge=1, le=5)


@router.post("/{contest_id}/tasks/{task_id}/rate", status_code=status.HTTP_204_NO_CONTENT)
async def rate_contest_task(
    contest_id: int,
    task_id: int,
    payload: TaskRatingRequest,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    user, profile = current_user_data
    rating_value = payload.rating

    existing = (
        await db.execute(
            select(ContestTaskRating).where(
                ContestTaskRating.contest_id == contest_id,
                ContestTaskRating.task_id == task_id,
                ContestTaskRating.user_id == user.id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.rating = rating_value
        existing.rated_at = datetime.now(timezone.utc)
    else:
        db.add(ContestTaskRating(
            contest_id=contest_id,
            task_id=task_id,
            user_id=user.id,
            rating=rating_value,
        ))

    await db.commit()
