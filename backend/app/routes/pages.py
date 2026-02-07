from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text, select, func, delete
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user, get_current_admin
from app.database import get_db
from app.models.user import User, UserProfile
from app.models.contest import (
    Contest,
    ContestTask,
    Task,
    TaskFlag,
    TaskAuthorSolution,
    LlmGeneration,
)
from app.schemas.admin import (
    AdminDashboardResponse,
    AdminStats,
    AdminFeedback,
    AdminChampionship,
    AdminArticle,
    AdminArticleCreateRequest,
    AdminArticleGenerateRequest,
    AdminArticleGenerateResponse,
    AdminNvdSync,
    AdminTaskGenerateRequest,
    AdminTaskGenerateResponse,
    AdminTaskCreateRequest,
    AdminTaskUpdateRequest,
    AdminTaskResponse,
    AdminTaskFlag,
    AdminContestListItem,
    AdminContestResponse,
    AdminContestCreateRequest,
    AdminContestUpdateRequest,
    AdminContestTaskResponse,
    AdminContestTask,
)
from app.services.nvd_sync import run_sync
from app.services.task_generation import generate_task_payload, TaskGenerationError
from app.services.article_generation import generate_article_payload, ArticleGenerationError

router = APIRouter(tags=["Тестовые страницы"])

@router.get("/welcome")
async def welcome_page(
    current_user_data: tuple = Depends(get_current_user)
):
    """
    Приветственная страница для авторизованных пользователей.
    Доступна всем (и admin, и participant).
    """
    user, profile = current_user_data
    
    return {
        "message": "Молодец, БД работает, добро пожаловать!",
        "user": {
            "username": profile.username,
            "email": user.email,
            "role": profile.role
        }
    }

@router.get("/admin", response_model=AdminDashboardResponse)
async def admin_panel(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Админка.
    Доступна только пользователям с ролью 'admin'.
    Возвращает метрики и данные для дашборда.
    """
    _user, _profile = current_user_data

    total_users = (await db.execute(text("SELECT COUNT(*) FROM users"))).scalar_one() or 0
    active_users = (
        await db.execute(
            text(
                """
                SELECT COUNT(*)
                FROM user_profiles
                WHERE last_login IS NOT NULL
                  AND last_login >= now() - INTERVAL '24 hours'
                """
            )
        )
    ).scalar_one() or 0
    paid_users = (
        await db.execute(
            text(
                """
                SELECT COUNT(DISTINCT ut.user_id)
                FROM user_tariffs ut
                JOIN tariff_plans tp ON tp.id = ut.tariff_id
                WHERE tp.code <> 'FREE'
                  AND ut.is_promo IS FALSE
                  AND ut.valid_from <= now()
                  AND (ut.valid_to IS NULL OR ut.valid_to > now())
                """
            )
        )
    ).scalar_one() or 0

    contest_row = (
        await db.execute(
            text(
                """
                SELECT id, title, description, start_at, end_at, is_public, leaderboard_visible
                FROM contests
                WHERE start_at <= now() AND end_at >= now()
                ORDER BY start_at DESC
                LIMIT 1
                """
            )
        )
    ).mappings().first()

    if contest_row is None:
        contest_row = (
            await db.execute(
                text(
                    """
                    SELECT id, title, description, start_at, end_at, is_public, leaderboard_visible
                    FROM contests
                    ORDER BY start_at DESC
                    LIMIT 1
                    """
                )
            )
        ).mappings().first()

    submissions_count = 0
    if contest_row is not None:
        submissions_count = (
            await db.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM submissions
                    WHERE contest_id = :contest_id
                    """
                ),
                {"contest_id": contest_row["id"]},
            )
        ).scalar_one() or 0

    feedback_rows = (
        await db.execute(
            text(
                """
                SELECT f.user_id, p.username, f.topic, f.message, f.created_at
                FROM feedback f
                LEFT JOIN user_profiles p ON p.user_id = f.user_id
                ORDER BY f.created_at DESC NULLS LAST
                LIMIT 4
                """
            )
        )
    ).mappings().all()

    latest_feedbacks = [
        AdminFeedback(
            user_id=row["user_id"],
            username=row.get("username"),
            topic=row["topic"],
            message=row["message"],
            created_at=row.get("created_at"),
        )
        for row in feedback_rows
    ]

    article_row = (
        await db.execute(
            text(
                """
                SELECT id, source, source_id, cve_id, ru_title, ru_summary, ru_explainer, created_at, updated_at
                FROM kb_entries
                ORDER BY COALESCE(updated_at, created_at) DESC
                LIMIT 1
                """
            )
        )
    ).mappings().first()

    nvd_row = None
    try:
        nvd_row = (
            await db.execute(
                text(
                    """
                    SELECT fetched_at, inserted_count, status
                    FROM nvd_sync_log
                    ORDER BY fetched_at DESC NULLS LAST
                    LIMIT 1
                    """
                )
            )
        ).mappings().first()
    except ProgrammingError as exc:
        error_text = str(exc)
        if "nvd_sync_log" not in error_text:
            raise

    return AdminDashboardResponse(
        stats=AdminStats(
            total_users=total_users,
            active_users_24h=active_users,
            paid_users=paid_users,
            current_championship_submissions=submissions_count,
        ),
        latest_feedbacks=latest_feedbacks,
        current_championship=AdminChampionship(**contest_row) if contest_row else None,
        last_article=AdminArticle(**article_row) if article_row else None,
        nvd_sync=(
            AdminNvdSync(
                last_fetch_at=nvd_row.get("fetched_at"),
                last_inserted=nvd_row.get("inserted_count"),
                status=nvd_row.get("status"),
            )
            if nvd_row
            else None
        ),
    )


def _normalize_tags(raw_tags: Optional[list[str]]) -> list[str]:
    tags = raw_tags or []
    return [tag.strip() for tag in tags if tag and tag.strip()]


def _coerce_task_kind(value: Optional[str]) -> str:
    if not value:
        return "contest"
    value = value.strip().lower()
    return value if value in {"contest", "practice"} else "contest"


def _task_to_response(
    task: Task,
    flags: Optional[list[TaskFlag]] = None,
    creation_solution: Optional[str] = None,
) -> AdminTaskResponse:
    return AdminTaskResponse(
        id=task.id,
        title=task.title,
        category=task.category,
        difficulty=task.difficulty,
        points=task.points,
        tags=task.tags or [],
        language=task.language,
        story=task.story,
        participant_description=task.participant_description,
        state=task.state,
        task_kind=task.task_kind or "contest",
        llm_raw_response=task.llm_raw_response,
        creation_solution=creation_solution,
        created_at=task.created_at,
        flags=[
            AdminTaskFlag(
                flag_id=flag.flag_id,
                format=flag.format,
                expected_value=flag.expected_value or "",
                description=flag.description,
            )
            for flag in (flags or [])
        ],
    )


@router.post("/admin/kb_entries", response_model=AdminArticle)
async def create_kb_entry(
    data: AdminArticleCreateRequest,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Создать запись в базе знаний.
    Доступно только admin.
    """
    _user, _profile = current_user_data

    source = (data.source or "").strip()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source is required",
        )

    tags = data.tags or []
    tags = [tag.strip() for tag in tags if tag and tag.strip()]

    row = (
        await db.execute(
            text(
                """
                INSERT INTO kb_entries
                    (source, source_id, cve_id, raw_en_text, ru_title, ru_summary, ru_explainer, tags, difficulty, updated_at)
                VALUES
                    (:source, :source_id, :cve_id, :raw_en_text, :ru_title, :ru_summary, :ru_explainer, :tags, :difficulty, now())
                RETURNING id, source, source_id, cve_id, raw_en_text, ru_title, ru_summary, ru_explainer, tags, difficulty, created_at, updated_at
                """
            ),
            {
                "source": source,
                "source_id": data.source_id,
                "cve_id": data.cve_id,
                "raw_en_text": data.raw_en_text,
                "ru_title": data.ru_title,
                "ru_summary": data.ru_summary,
                "ru_explainer": data.ru_explainer,
                "tags": tags,
                "difficulty": data.difficulty,
            },
        )
    ).mappings().first()

    await db.commit()

    return AdminArticle(**row)


@router.get("/admin/kb_entries", response_model=list[AdminArticle])
async def list_kb_entries_admin(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    limit: int = 100,
    offset: int = 0,
):
    """
    Список статей для админки.
    """
    _user, _profile = current_user_data

    rows = (
        await db.execute(
            text(
                """
                SELECT id, source, source_id, cve_id, raw_en_text, ru_title, ru_summary, ru_explainer, tags, difficulty, created_at, updated_at
                FROM kb_entries
                ORDER BY COALESCE(updated_at, created_at) DESC
                LIMIT :limit
                OFFSET :offset
                """
            ),
            {"limit": limit, "offset": offset},
        )
    ).mappings().all()

    return [AdminArticle(**row) for row in rows]


@router.put("/admin/kb_entries/{entry_id}", response_model=AdminArticle)
async def update_kb_entry(
    entry_id: int,
    data: AdminArticleCreateRequest,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновить запись базы знаний.
    """
    _user, _profile = current_user_data

    source = (data.source or "").strip()
    if not source:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="source is required",
        )

    tags = data.tags or []
    tags = [tag.strip() for tag in tags if tag and tag.strip()]

    row = (
        await db.execute(
            text(
                """
                UPDATE kb_entries
                SET source = :source,
                    source_id = :source_id,
                    cve_id = :cve_id,
                    raw_en_text = :raw_en_text,
                    ru_title = :ru_title,
                    ru_summary = :ru_summary,
                    ru_explainer = :ru_explainer,
                    tags = :tags,
                    difficulty = :difficulty,
                    updated_at = now()
                WHERE id = :entry_id
                RETURNING id, source, source_id, cve_id, raw_en_text, ru_title, ru_summary, ru_explainer, tags, difficulty, created_at, updated_at
                """
            ),
            {
                "entry_id": entry_id,
                "source": source,
                "source_id": data.source_id,
                "cve_id": data.cve_id,
                "raw_en_text": data.raw_en_text,
                "ru_title": data.ru_title,
                "ru_summary": data.ru_summary,
                "ru_explainer": data.ru_explainer,
                "tags": tags,
                "difficulty": data.difficulty,
            },
        )
    ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Статья не найдена",
        )

    await db.commit()

    return AdminArticle(**row)


@router.post("/admin/kb_entries/generate", response_model=AdminArticleGenerateResponse)
async def generate_kb_entry_fields(
    data: AdminArticleGenerateRequest,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Сгенерировать RU заголовок/summary/explainer из Raw EN текста.
    """
    user, _profile = current_user_data

    raw_text = (data.raw_en_text or "").strip()
    if not raw_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="raw_en_text is required")

    try:
        result = await generate_article_payload(raw_text)
    except ArticleGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    generation = LlmGeneration(
        model=result["model"],
        purpose="kb_explainer",
        input_payload=result["input"],
        output_payload=result["parsed"],
        created_by=user.id,
    )
    db.add(generation)
    await db.commit()

    parsed = result["parsed"] or {}
    return AdminArticleGenerateResponse(
        ru_title=parsed.get("ru_title") or "",
        ru_summary=parsed.get("ru_summary") or "",
        ru_explainer=parsed.get("ru_explainer") or "",
        tags=parsed.get("tags") or [],
        model=result["model"],
        raw_text=result["raw_text"],
    )


@router.post("/admin/nvd_sync", response_model=AdminNvdSync)
async def sync_nvd_last_24h(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Запустить синхронизацию NVD за последние 24 часа.
    """
    _user, _profile = current_user_data

    fetched_at = datetime.now(timezone.utc)
    status_value = "success"
    inserted_count = None
    window_start = None
    window_end = None
    error_text = None

    try:
        result = await run_sync(hours=24)
        inserted_count = result.get("inserted")
        window_start = result.get("window_start")
        window_end = result.get("window_end")
    except Exception as exc:  # noqa: BLE001 - surface error to log table
        status_value = "failed"
        error_text = str(exc)[:500]

    try:
        await db.execute(
            text(
                """
                INSERT INTO nvd_sync_log (fetched_at, window_start, window_end, inserted_count, status, error)
                VALUES (:fetched_at, :window_start, :window_end, :inserted_count, :status, :error)
                """
            ),
            {
                "fetched_at": fetched_at,
                "window_start": window_start,
                "window_end": window_end,
                "inserted_count": inserted_count,
                "status": status_value,
                "error": error_text,
            },
        )
        await db.commit()
    except ProgrammingError as exc:
        error_text = str(exc)
        if "nvd_sync_log" in error_text:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="nvd_sync_log table missing. Apply schema.sql changes.",
            ) from exc
        raise

    if status_value != "success":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Не удалось синхронизировать NVD",
        )

    return AdminNvdSync(
        last_fetch_at=fetched_at,
        last_inserted=inserted_count,
        status=status_value,
    )


@router.get("/admin/tasks", response_model=list[AdminTaskResponse])
async def list_admin_tasks(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    task_kind: Optional[str] = None,
    state: Optional[str] = None,
    category: Optional[str] = None,
    tags: Optional[str] = None,
):
    """
    Список задач для админки.
    """
    _user, _profile = current_user_data

    query = select(Task).order_by(Task.created_at.desc())

    if task_kind:
        query = query.where(Task.task_kind == task_kind)
    if state:
        query = query.where(Task.state == state)
    if category:
        query = query.where(Task.category == category)
    if tags:
        parsed_tags = [tag.strip() for tag in tags.split(",") if tag.strip()]
        if parsed_tags:
            query = query.where(Task.tags.overlap(parsed_tags))

    rows = (await db.execute(query)).scalars().all()
    return [_task_to_response(task) for task in rows]


@router.post("/admin/tasks/generate", response_model=AdminTaskGenerateResponse)
async def generate_admin_task(
    data: AdminTaskGenerateRequest,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Генерация задачи через Yandex Cloud LLM.
    """
    user, _profile = current_user_data

    if data.difficulty < 1 or data.difficulty > 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="difficulty must be 1..10")

    tags = _normalize_tags(data.tags)

    try:
        result = await generate_task_payload(data.difficulty, tags, data.description)
    except TaskGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc

    generation = LlmGeneration(
        model=result["model"],
        purpose="task_generation",
        input_payload=result["input"],
        output_payload=result["parsed"],
        created_by=user.id,
    )
    db.add(generation)
    await db.commit()

    return AdminTaskGenerateResponse(
        model=result["model"],
        task=result["parsed"],
        raw_text=result["raw_text"],
    )


@router.post("/admin/tasks", response_model=AdminTaskResponse)
async def create_admin_task(
    data: AdminTaskCreateRequest,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Создать задачу (включая флаги).
    """
    user, _profile = current_user_data

    tags = _normalize_tags(data.tags)
    task_kind = _coerce_task_kind(data.task_kind)

    if not data.flags or any(not flag.expected_value for flag in data.flags):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="flags are required")
    if not data.title or not data.category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title and category are required")

    task = Task(
        title=data.title.strip(),
        category=data.category.strip(),
        difficulty=data.difficulty,
        points=data.points,
        tags=tags,
        language=data.language,
        story=data.story,
        participant_description=data.participant_description,
        state=data.state,
        task_kind=task_kind,
        llm_raw_response=data.llm_raw_response,
        created_by=user.id,
    )
    db.add(task)
    await db.flush()

    if data.creation_solution:
        db.add(
            TaskAuthorSolution(
                task_id=task.id,
                creation_solution=data.creation_solution,
            )
        )

    for flag in data.flags:
        db.add(
            TaskFlag(
                task_id=task.id,
                flag_id=flag.flag_id,
                format=flag.format,
                expected_value=flag.expected_value.strip(),
                description=flag.description,
            )
        )

    await db.commit()
    await db.refresh(task)

    flags = (
        await db.execute(select(TaskFlag).where(TaskFlag.task_id == task.id))
    ).scalars().all()

    return _task_to_response(task, flags, data.creation_solution)


@router.put("/admin/tasks/{task_id}", response_model=AdminTaskResponse)
async def update_admin_task(
    task_id: int,
    data: AdminTaskUpdateRequest,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновить задачу (базовая задача, не контест-override).
    """
    _user, _profile = current_user_data

    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")

    if data.title is not None:
        task.title = data.title.strip()
    if data.category is not None:
        task.category = data.category.strip()
    if data.difficulty is not None:
        task.difficulty = data.difficulty
    if data.points is not None:
        task.points = data.points
    if data.tags is not None:
        task.tags = _normalize_tags(data.tags)
    if data.language is not None:
        task.language = data.language
    if data.story is not None:
        task.story = data.story
    if data.participant_description is not None:
        task.participant_description = data.participant_description
    if data.state is not None:
        task.state = data.state
    if data.task_kind is not None:
        task.task_kind = _coerce_task_kind(data.task_kind)
    if data.llm_raw_response is not None:
        task.llm_raw_response = data.llm_raw_response

    if data.creation_solution is not None:
        solution = (
            await db.execute(
                select(TaskAuthorSolution).where(TaskAuthorSolution.task_id == task.id)
            )
        ).scalar_one_or_none()
        if solution is None:
            solution = TaskAuthorSolution(task_id=task.id)
            db.add(solution)
        solution.creation_solution = data.creation_solution

    if data.flags is not None:
        await db.execute(delete(TaskFlag).where(TaskFlag.task_id == task.id))
        for flag in data.flags:
            db.add(
                TaskFlag(
                    task_id=task.id,
                    flag_id=flag.flag_id,
                    format=flag.format,
                    expected_value=flag.expected_value.strip(),
                    description=flag.description,
                )
            )

    await db.commit()
    await db.refresh(task)

    flags = (
        await db.execute(select(TaskFlag).where(TaskFlag.task_id == task.id))
    ).scalars().all()
    solution = (
        await db.execute(
            select(TaskAuthorSolution).where(TaskAuthorSolution.task_id == task.id)
        )
    ).scalar_one_or_none()

    return _task_to_response(task, flags, solution.creation_solution if solution else None)


@router.get("/admin/contests", response_model=list[AdminContestListItem])
async def list_admin_contests(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Список контестов для админки.
    """
    _user, _profile = current_user_data

    rows = (
        await db.execute(
            select(Contest, func.count(ContestTask.task_id))
            .outerjoin(ContestTask, ContestTask.contest_id == Contest.id)
            .group_by(Contest.id)
            .order_by(Contest.start_at.desc())
        )
    ).all()

    now = datetime.now(timezone.utc)
    items: list[AdminContestListItem] = []
    for contest, tasks_count in rows:
        start_at = contest.start_at.replace(tzinfo=timezone.utc) if contest.start_at.tzinfo is None else contest.start_at
        end_at = contest.end_at.replace(tzinfo=timezone.utc) if contest.end_at.tzinfo is None else contest.end_at
        if now < start_at:
            status_value = "upcoming"
        elif now > end_at:
            status_value = "finished"
        else:
            status_value = "active"
        items.append(
            AdminContestListItem(
                id=contest.id,
                title=contest.title,
                description=contest.description,
                start_at=contest.start_at,
                end_at=contest.end_at,
                is_public=contest.is_public,
                leaderboard_visible=contest.leaderboard_visible,
                status=status_value,
                tasks_count=tasks_count or 0,
            )
        )
    return items


@router.get("/admin/contests/{contest_id}", response_model=AdminContestResponse)
async def get_admin_contest(
    contest_id: int,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Детали контеста для админки.
    """
    _user, _profile = current_user_data

    contest = (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none()
    if contest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Контест не найден")

    rows = (
        await db.execute(
            select(ContestTask, Task)
            .join(Task, Task.id == ContestTask.task_id)
            .where(ContestTask.contest_id == contest_id)
            .order_by(ContestTask.order_index.asc())
        )
    ).all()

    tasks = []
    for contest_task, task in rows:
        tasks.append(
            AdminContestTaskResponse(
                task_id=contest_task.task_id,
                order_index=contest_task.order_index,
                points_override=contest_task.points_override,
                override_title=contest_task.override_title,
                override_participant_description=contest_task.override_participant_description,
                override_tags=contest_task.override_tags,
                override_category=contest_task.override_category,
                override_difficulty=contest_task.override_difficulty,
                title=task.title,
                category=task.category,
                difficulty=task.difficulty,
                points=task.points,
                tags=task.tags,
                participant_description=task.participant_description,
            )
        )

    return AdminContestResponse(
        id=contest.id,
        title=contest.title,
        description=contest.description,
        start_at=contest.start_at,
        end_at=contest.end_at,
        is_public=contest.is_public,
        leaderboard_visible=contest.leaderboard_visible,
        tasks=tasks,
    )


def _validate_contest_tasks(tasks: list[AdminContestTask]) -> None:
    if not (2 <= len(tasks) <= 10):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Контест должен иметь 2-10 задач")


@router.post("/admin/contests", response_model=AdminContestResponse)
async def create_admin_contest(
    data: AdminContestCreateRequest,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Создать контест с задачами.
    """
    _user, _profile = current_user_data

    _validate_contest_tasks(data.tasks)

    contest = Contest(
        title=data.title,
        description=data.description,
        start_at=data.start_at,
        end_at=data.end_at,
        is_public=data.is_public,
        leaderboard_visible=data.leaderboard_visible,
    )
    db.add(contest)
    await db.flush()

    for item in data.tasks:
        task = (await db.execute(select(Task).where(Task.id == item.task_id))).scalar_one_or_none()
        if task is None:
            raise HTTPException(status_code=404, detail=f"Задача {item.task_id} не найдена")
        if task.task_kind != "contest":
            raise HTTPException(status_code=400, detail="Можно добавлять только contest-задачи")
        db.add(
            ContestTask(
                contest_id=contest.id,
                task_id=item.task_id,
                order_index=item.order_index,
                points_override=item.points_override,
                override_title=item.override_title,
                override_participant_description=item.override_participant_description,
                override_tags=item.override_tags,
                override_category=item.override_category,
                override_difficulty=item.override_difficulty,
            )
        )

    await db.commit()
    await db.refresh(contest)

    return await get_admin_contest(contest.id, current_user_data, db)


@router.put("/admin/contests/{contest_id}", response_model=AdminContestResponse)
async def update_admin_contest(
    contest_id: int,
    data: AdminContestUpdateRequest,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновить контест и его задачи.
    """
    _user, _profile = current_user_data

    contest = (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none()
    if contest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Контест не найден")

    if data.title is not None:
        contest.title = data.title
    if data.description is not None:
        contest.description = data.description
    if data.start_at is not None:
        contest.start_at = data.start_at
    if data.end_at is not None:
        contest.end_at = data.end_at
    if data.is_public is not None:
        contest.is_public = data.is_public
    if data.leaderboard_visible is not None:
        contest.leaderboard_visible = data.leaderboard_visible

    if data.tasks is not None:
        _validate_contest_tasks(data.tasks)
        await db.execute(delete(ContestTask).where(ContestTask.contest_id == contest_id))
        for item in data.tasks:
            task = (await db.execute(select(Task).where(Task.id == item.task_id))).scalar_one_or_none()
            if task is None:
                raise HTTPException(status_code=404, detail=f"Задача {item.task_id} не найдена")
            if task.task_kind != "contest":
                raise HTTPException(status_code=400, detail="Можно добавлять только contest-задачи")
            db.add(
                ContestTask(
                    contest_id=contest_id,
                    task_id=item.task_id,
                    order_index=item.order_index,
                    points_override=item.points_override,
                    override_title=item.override_title,
                    override_participant_description=item.override_participant_description,
                    override_tags=item.override_tags,
                    override_category=item.override_category,
                    override_difficulty=item.override_difficulty,
                )
            )

    await db.commit()

    return await get_admin_contest(contest_id, current_user_data, db)
