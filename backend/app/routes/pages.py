from datetime import datetime, timezone
import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import text, select, func, delete, update
from sqlalchemy.exc import ProgrammingError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user, get_current_admin
from app.config import settings
from app.database import get_db, AsyncSessionLocal, ensure_nvd_sync_schema_compatibility
from app.models.user import User, UserProfile
from app.models.activity import ActivityLog, EventType, EventSource
from app.models.contest import (
    Contest,
    ContestTask,
    ContestParticipant,
    Task,
    TaskFlag,
    TaskMaterial,
    TaskAuthorSolution,
    Submission,
    LlmGeneration,
    PromptTemplate,
    ContestGenJob,
)
from app.schemas.admin import (
    AdminDashboardResponse,
    AdminStats,
    AdminFeedback,
    AdminComment,
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
    AdminTaskMaterial,
    AdminContestListItem,
    AdminContestResponse,
    AdminContestCreateRequest,
    AdminContestUpdateRequest,
    AdminContestTaskResponse,
    AdminContestTask,
    AdminPromptTemplate,
    AdminPromptUpdateRequest,
    AdminChatModelResponse,
    AdminChatModelUpdate,
    AdminTaskModelResponse,
    AdminTaskModelUpdate,
    AdminTranslationModelResponse,
    AdminTranslationModelUpdate,
    ActivityLogItemResponse,
    ActivityLogListResponse,
    CveSearchResult,
    ProRequestItem,
    ChampionshipGenerateRequest,
    ChampionshipGenerateResponse,
    ChampionshipGenStartResponse,
    ChampionshipGenJobStatus,
)
from app.services.championship_generation import (
    generate_championship_task,
    materialize_championship_task,
    select_kb_entry_clusters,
    ChampionshipGenerationError,
)
from app.services.championship_job_runner import launch_generation_job
from app.services.nvd_sync import (
    create_sync_log,
    create_translate_log,
    create_embed_log,
    get_latest_sync_log,
    run_fetch_only_background,
    run_translate_standalone_background,
    run_embed_standalone_background,
    stop_active_sync_log,
    sync_log_to_admin_payload,
)
from app.services.task_generation import (
    generate_task_payload_with_prompt,
    get_active_task_model_key,
    TASK_MODEL_REGISTRY,
    TaskGenerationError,
)
from app.services.ai_generator.translation_service import (
    get_active_translation_model_key,
    TRANSLATION_MODEL_REGISTRY,
)
from app.services.article_generation import (
    generate_article_payload_with_prompt,
    ArticleGenerationError,
)
from app.services.chat_task import (
    ChatTaskConfigError,
    CHAT_MODEL_REGISTRY,
    DEFAULT_CHAT_MODEL_KEY,
    DEFAULT_CHAT_MODEL_MAX_OUTPUT_TOKENS,
    DEFAULT_CHAT_SESSION_TTL_MINUTES,
    DEFAULT_CHAT_USER_MESSAGE_MAX_CHARS,
    get_active_chat_model_key,
    validate_chat_task_config_values,
)
from app.services.prompt_loader import load_prompt_text, PromptLoadError
from app.services.activity_logger import (
    log_contest_created,
    log_contest_updated,
    log_contest_deleted,
    log_contest_ended,
)

router = APIRouter(tags=["Тестовые страницы"])
logger = logging.getLogger(__name__)

# Сохраняем сильные ссылки на асинхронные задачи, чтобы они пережили отключение клиента
_nvd_background_tasks: set[asyncio.Task] = set()


def _admin_nvd_sync_from_row(row: Optional[dict]) -> Optional[AdminNvdSync]:
    payload = sync_log_to_admin_payload(row)
    return AdminNvdSync(**payload) if payload else None

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

    # Параллельное выполнение независимых запросов через отдельные сессии.
    # AsyncSession не допускает параллельных await на одном соединении,
    # поэтому каждый запрос получает собственную сессию из пула.
    async def _fetch_metrics(s: AsyncSession):
        row = (await s.execute(text(
            """
            SELECT
              (SELECT COUNT(*) FROM users) AS total_users,
              (SELECT COUNT(*) FROM users
                 WHERE email NOT LIKE '%@seed.local') AS real_users,
              (SELECT COUNT(*) FROM user_profiles
                 WHERE last_login IS NOT NULL
                   AND last_login >= now() - INTERVAL '24 hours') AS active_users,
              (SELECT COUNT(DISTINCT ut.user_id)
                 FROM user_tariffs ut
                 JOIN tariff_plans tp ON tp.id = ut.tariff_id
                 WHERE tp.code <> 'FREE'
                   AND ut.is_promo IS FALSE
                   AND ut.valid_from <= now()
                   AND (ut.valid_to IS NULL OR ut.valid_to > now())) AS paid_users,
              (SELECT COUNT(*) FROM user_profiles
                 WHERE sub_request = TRUE) AS pro_requests
            """
        ))).mappings().one()
        return row

    async def _fetch_contest(s: AsyncSession):
        row = (await s.execute(text(
            """
            SELECT id, title, description, start_at, end_at, is_public, leaderboard_visible
            FROM contests
            WHERE start_at <= now() AND end_at >= now()
            ORDER BY start_at DESC
            LIMIT 1
            """
        ))).mappings().first()
        if row is None:
            row = (await s.execute(text(
                """
                SELECT id, title, description, start_at, end_at, is_public, leaderboard_visible
                FROM contests
                ORDER BY start_at DESC
                LIMIT 1
                """
            ))).mappings().first()
        return row

    async def _fetch_feedbacks(s: AsyncSession):
        return (await s.execute(text(
            """
            SELECT f.id, f.user_id, p.username, f.topic, f.message,
                   COALESCE(f.resolved, FALSE) AS resolved, f.created_at
            FROM feedback f
            LEFT JOIN user_profiles p ON p.user_id = f.user_id
            WHERE COALESCE(f.resolved, FALSE) = FALSE
            ORDER BY f.created_at DESC NULLS LAST
            LIMIT 8
            """
        ))).mappings().all()

    async def _fetch_article(s: AsyncSession):
        return (await s.execute(text(
            """
            SELECT id, source, source_id, cve_id, ru_title, ru_summary, ru_explainer, created_at, updated_at
            FROM kb_entries
            ORDER BY COALESCE(updated_at, created_at) DESC
            LIMIT 1
            """
        ))).mappings().first()

    async def _fetch_nvd(s: AsyncSession):
        try:
            return await get_latest_sync_log(s)
        except ProgrammingError as exc:
            if "nvd_sync_log" not in str(exc):
                raise
            return None

    async def _run(fn):
        async with AsyncSessionLocal() as s:
            return await fn(s)

    metrics_row, contest_row, feedback_rows, article_row, nvd_row = await asyncio.gather(
        _run(_fetch_metrics),
        _run(_fetch_contest),
        _run(_fetch_feedbacks),
        _run(_fetch_article),
        _run(_fetch_nvd),
    )

    total_users = metrics_row["total_users"] or 0
    real_users = metrics_row["real_users"] or 0
    active_users = metrics_row["active_users"] or 0
    paid_users = metrics_row["paid_users"] or 0
    pro_requests = metrics_row["pro_requests"] or 0

    # submissions зависит от contest_id — делаем отдельный запрос после gather
    submissions_count = 0
    if contest_row is not None:
        submissions_count = (
            await db.execute(
                text("SELECT COUNT(*) FROM submissions WHERE contest_id = :cid"),
                {"cid": contest_row["id"]},
            )
        ).scalar_one() or 0

    latest_feedbacks = [
        AdminFeedback(
            id=row["id"],
            user_id=row["user_id"],
            username=row.get("username"),
            topic=row["topic"],
            message=row["message"],
            resolved=bool(row.get("resolved")),
            created_at=row.get("created_at"),
        )
        for row in feedback_rows
    ]

    return AdminDashboardResponse(
        stats=AdminStats(
            total_users=total_users,
            real_users=real_users,
            active_users_24h=active_users,
            paid_users=paid_users,
            current_championship_submissions=submissions_count,
            pro_requests=pro_requests,
        ),
        latest_feedbacks=latest_feedbacks,
        current_championship=AdminChampionship(**contest_row) if contest_row else None,
        last_article=AdminArticle(**article_row) if article_row else None,
        nvd_sync=_admin_nvd_sync_from_row(nvd_row),
    )


@router.post("/admin/feedback/{feedback_id}/resolve", response_model=AdminFeedback)
async def resolve_feedback(
    feedback_id: int,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Отметить сообщение обратной связи как resolved.
    """
    _user, _profile = current_user_data

    row = (
        await db.execute(
            text(
                """
                UPDATE feedback
                SET resolved = TRUE
                WHERE id = :feedback_id
                RETURNING id, user_id, topic, message, COALESCE(resolved, FALSE) AS resolved, created_at
                """
            ),
            {"feedback_id": feedback_id},
        )
    ).mappings().first()

    if not row:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Отзыв не найден",
        )

    username = (
        await db.execute(
            text("SELECT username FROM user_profiles WHERE user_id = :user_id"),
            {"user_id": row["user_id"]},
        )
    ).scalar_one_or_none()

    await db.commit()

    return AdminFeedback(
        id=row["id"],
        user_id=row["user_id"],
        username=username,
        topic=row["topic"],
        message=row["message"],
        resolved=bool(row.get("resolved")),
        created_at=row.get("created_at"),
    )

@router.get("/admin/feedbacks", response_model=list[AdminFeedback])
async def list_feedbacks_admin(
    resolved: Optional[bool] = Query(None, description="Фильтр по статусу решения"),
    limit: int = 100,
    offset: int = 0,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить все отзывы (пагинация).
    """
    _user, _profile = current_user_data

    rows = (
        await db.execute(
            text("""
                SELECT f.id, f.user_id, p.username, f.topic, f.message, COALESCE(f.resolved, FALSE) AS resolved, f.created_at
                FROM feedback f
                LEFT JOIN user_profiles p ON p.user_id = f.user_id
                WHERE (CAST(:resolved AS boolean) IS NULL OR COALESCE(f.resolved, FALSE) = CAST(:resolved AS boolean))
                ORDER BY f.created_at DESC
                LIMIT :limit OFFSET :offset
                """),
            {"resolved": resolved, "limit": limit, "offset": offset},
        )
    ).mappings().all()

    return [AdminFeedback(**row) for row in rows]


@router.get("/admin/comments", response_model=list[AdminComment])
async def list_comments_admin(
    kb_entry_id: Optional[int] = Query(None, description="Фильтр комментариев по статье базы знаний"),
    limit: int = 100,
    offset: int = 0,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить все комментарии к статьям (пагинация).
    """
    _user, _profile = current_user_data

    rows = (
        await db.execute(
            text("""
                SELECT c.*, p.username, p.avatar_url, k.ru_title as entry_title
                FROM kb_comments c
                LEFT JOIN user_profiles p ON p.user_id = c.user_id
                LEFT JOIN kb_entries k ON k.id = c.kb_entry_id
                WHERE (CAST(:kb_entry_id AS integer) IS NULL OR c.kb_entry_id = CAST(:kb_entry_id AS integer))
                ORDER BY c.created_at DESC
                LIMIT :limit OFFSET :offset
                """),
            {"kb_entry_id": kb_entry_id, "limit": limit, "offset": offset},
        )
    ).mappings().all()

    return [AdminComment(**row) for row in rows]



def _normalize_tags(raw_tags: Optional[list[str]]) -> list[str]:
    tags = raw_tags or []
    return [tag.strip() for tag in tags if tag and tag.strip()]


def _coerce_task_kind(value: Optional[str]) -> str:
    if not value:
        return "contest"
    value = value.strip().lower()
    return value if value in {"contest", "practice", "ugc"} else "contest"


def _coerce_access_type(value: Optional[str]) -> str:
    if not value:
        return "just_flag"
    value = value.strip().lower()
    allowed = {"vpn", "vm", "link", "file", "chat", "just_flag"}
    return value if value in allowed else "just_flag"


def _build_chat_flags() -> list[dict]:
    return [
        {
            "flag_id": "main",
            "format": "FLAG{8HEX}",
            "expected_value": None,
            "description": "Dynamic session flag",
        }
    ]


def _normalize_task_materials(raw_materials: Optional[list[AdminTaskMaterial]]) -> list[dict]:
    normalized: list[dict] = []
    for item in raw_materials or []:
        item_type = (item.type or "").strip().lower()
        name = (item.name or "").strip()
        if not item_type or not name:
            continue

        raw_meta = item.meta if isinstance(item.meta, dict) else None
        meta = raw_meta if raw_meta else None

        normalized.append(
            {
                "type": item_type,
                "name": name,
                "description": (item.description or "").strip() or None,
                "url": (item.url or "").strip() or None,
                "storage_key": (item.storage_key or "").strip() or None,
                "meta": meta,
            }
        )
    return normalized


PROMPT_SPECS = [
    {
        "code": "task_prompt",
        "title": "Промпт генерации задач",
        "description": "Системный промпт для генерации контестных/практических задач из билдера админки.",
        "filename": "task_prompt.txt",
    },
    {
        "code": "article_prompt",
        "title": "Промпт генерации статей",
        "description": "Системный промпт для генерации RU заголовка, summary, explainer и тегов из сырого EN-текста.",
        "filename": "article_prompt.txt",
    },
    {
        "code": "championship_prompt",
        "title": "Промпт генерации чемпионатных задач",
        "description": "Системный промпт для генерации многоэтапных чемпионатных задач по нескольким CVE.",
        "filename": "championship_prompt.txt",
    },
]
PROMPT_SPEC_BY_CODE = {item["code"]: item for item in PROMPT_SPECS}


async def _fetch_prompt_overrides(db: AsyncSession) -> tuple[dict[str, PromptTemplate], bool]:
    """
    Возвращает переопределения промптов и флаг доступности таблицы prompt_templates.
    """
    try:
        rows = (await db.execute(select(PromptTemplate))).scalars().all()
    except ProgrammingError as exc:
        if "prompt_templates" in str(exc):
            await db.rollback()
            return {}, False
        raise
    return {row.code: row for row in rows}, True


async def _resolve_prompt_text(db: AsyncSession, code: str) -> str:
    spec = PROMPT_SPEC_BY_CODE.get(code)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")

    overrides, _ = await _fetch_prompt_overrides(db)
    override = overrides.get(code)
    if override and (override.content or "").strip():
        return override.content.strip()

    try:
        return load_prompt_text(spec["filename"])
    except PromptLoadError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"{spec['filename']} not found and no DB override exists",
        ) from exc


def _task_to_response(
    task: Task,
    flags: Optional[list[TaskFlag]] = None,
    materials: Optional[list[TaskMaterial]] = None,
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
        parent_id=task.parent_id,
        access_type=task.access_type or "just_flag",
        chat_system_prompt_template=task.chat_system_prompt_template,
        chat_user_message_max_chars=task.chat_user_message_max_chars or DEFAULT_CHAT_USER_MESSAGE_MAX_CHARS,
        chat_model_max_output_tokens=task.chat_model_max_output_tokens or DEFAULT_CHAT_MODEL_MAX_OUTPUT_TOKENS,
        chat_session_ttl_minutes=task.chat_session_ttl_minutes or DEFAULT_CHAT_SESSION_TTL_MINUTES,
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
        materials=[
            AdminTaskMaterial(
                id=material.id,
                type=material.type,
                name=material.name,
                description=material.description,
                url=material.url,
                storage_key=material.storage_key,
                meta=material.meta if isinstance(material.meta, dict) else None,
            )
            for material in (materials or [])
        ],
    )


def _format_db_error(exc: Exception) -> str:
    return str(getattr(exc, "orig", exc))


def _validate_chat_fields_or_400(
    *,
    access_type: str,
    chat_system_prompt_template: Optional[str],
    chat_user_message_max_chars: Optional[int],
    chat_model_max_output_tokens: Optional[int],
    chat_session_ttl_minutes: Optional[int],
) -> tuple[Optional[str], int, int, int]:
    try:
        prompt_text, limits = validate_chat_task_config_values(
            access_type=access_type,
            chat_system_prompt_template=chat_system_prompt_template,
            chat_user_message_max_chars=(
                chat_user_message_max_chars
                if chat_user_message_max_chars is not None
                else DEFAULT_CHAT_USER_MESSAGE_MAX_CHARS
            ),
            chat_model_max_output_tokens=(
                chat_model_max_output_tokens
                if chat_model_max_output_tokens is not None
                else DEFAULT_CHAT_MODEL_MAX_OUTPUT_TOKENS
            ),
            chat_session_ttl_minutes=(
                chat_session_ttl_minutes
                if chat_session_ttl_minutes is not None
                else DEFAULT_CHAT_SESSION_TTL_MINUTES
            ),
        )
    except ChatTaskConfigError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return (
        prompt_text,
        limits.user_message_max_chars,
        limits.model_max_output_tokens,
        limits.session_ttl_minutes,
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


@router.get("/admin/cve_search", response_model=list[CveSearchResult])
async def search_cves(
    q: str = Query("", min_length=0),
    limit: int = Query(20, ge=1, le=100),
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Поиск kb_entries по CVE ID или тексту заголовка. Пустой q возвращает самые новые записи."""
    _user, _profile = current_user_data
    if q.strip():
        sql = text(
            """
            SELECT id, cve_id, ru_title, ru_summary
            FROM kb_entries
            WHERE cve_id ILIKE :q OR ru_title ILIKE :q
            ORDER BY COALESCE(updated_at, created_at) DESC
            LIMIT :limit
            """
        )
        params = {"q": f"%{q.strip()}%", "limit": limit}
    else:
        sql = text(
            """
            SELECT id, cve_id, ru_title, ru_summary
            FROM kb_entries
            ORDER BY COALESCE(updated_at, created_at) DESC
            LIMIT :limit
            """
        )
        params = {"limit": limit}
    rows = (await db.execute(sql, params)).mappings().all()
    return [CveSearchResult(**row) for row in rows]


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


@router.delete("/admin/kb_entries/{entry_id}")
async def delete_kb_entry(
    entry_id: int,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Удалить запись базы знаний.
    Связанные ссылки в задачах/LLM-логах обнуляются, чтобы не ломать FK.
    """
    _user, _profile = current_user_data

    row = (
        await db.execute(
            text("SELECT id FROM kb_entries WHERE id = :entry_id"),
            {"entry_id": entry_id},
        )
    ).first()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Статья не найдена")

    try:
        await db.execute(
            update(Task)
            .where(Task.kb_entry_id == entry_id)
            .values(kb_entry_id=None)
        )
        await db.execute(
            update(LlmGeneration)
            .where(LlmGeneration.kb_entry_id == entry_id)
            .values(kb_entry_id=None)
        )
        await db.execute(
            text("DELETE FROM kb_entries WHERE id = :entry_id"),
            {"entry_id": entry_id},
        )
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось удалить статью: {exc}",
        ) from exc

    return {"ok": True, "deleted_id": entry_id}


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
        prompt_text = await _resolve_prompt_text(db, "article_prompt")
        platform_model_key = await get_active_task_model_key(db)
        folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
        platform_model_uri = TASK_MODEL_REGISTRY[platform_model_key](folder)
        result = await generate_article_payload_with_prompt(raw_text, prompt_text, platform_model_uri)
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


@router.get("/admin/nvd_sync", response_model=Optional[AdminNvdSync])
async def get_nvd_sync_status(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Вернуть статус последней синхронизации NVD, включая прогресс embeddings.
    """
    _user, _profile = current_user_data

    try:
        row = await get_latest_sync_log(db)
    except ProgrammingError as exc:
        error_text = str(exc)
        if "nvd_sync_log" in error_text:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="nvd_sync_log table missing. Apply schema.sql changes.",
            ) from exc
        raise

    untranslated = (
        await db.execute(text("SELECT COUNT(*) FROM kb_entries WHERE source = 'nvd' AND ru_summary IS NULL"))
    ).scalar_one()

    payload = sync_log_to_admin_payload(row) or {}
    payload["untranslated_count"] = untranslated
    return AdminNvdSync(**payload)


@router.post("/admin/nvd_sync", response_model=AdminNvdSync, status_code=status.HTTP_202_ACCEPTED)
async def sync_nvd_last_24h(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Запустить фоновую синхронизацию NVD за последние 24 часа.
    """
    _user, _profile = current_user_data
    await ensure_nvd_sync_schema_compatibility()

    try:
        active_row = await get_latest_sync_log(db, active_only=True)
        if active_row:
            active_payload = sync_log_to_admin_payload(active_row)
            return AdminNvdSync(**active_payload)

        created_row = await create_sync_log(db)
    except ProgrammingError as exc:
        error_text = str(exc)
        if "nvd_sync_log" in error_text:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="nvd_sync_log table missing. Apply schema.sql changes.",
            ) from exc
        raise

    task = asyncio.create_task(run_fetch_only_background(created_row["id"], hours=24, date_filter="published"))
    _nvd_background_tasks.add(task)
    task.add_done_callback(_nvd_background_tasks.discard)
    created_payload = sync_log_to_admin_payload(created_row)
    return AdminNvdSync(**created_payload)


@router.delete("/admin/kb_entries/purge_by_date", status_code=status.HTTP_200_OK)
async def purge_kb_entries_by_date(
    date: str = Query(..., description="ISO date, e.g. 2026-04-16"),
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        text("DELETE FROM kb_entries WHERE created_at::date = :date"),
        {"date": date},
    )
    await db.commit()
    return {"deleted": result.rowcount}


@router.post("/admin/nvd_sync/stop", response_model=Optional[AdminNvdSync])
async def stop_nvd_sync(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Отметить активную синхронизацию как отменённую. Фоновая задача остановится на следующей границе чанка."""
    _user, _profile = current_user_data
    row = await stop_active_sync_log(db)
    return _admin_nvd_sync_from_row(row)


@router.post("/admin/nvd_sync/translate", response_model=AdminNvdSync, status_code=status.HTTP_202_ACCEPTED)
async def translate_nvd_entries(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    limit: Optional[int] = Query(None, ge=1, le=50000),
):
    """Перевести kb_entries без ru_summary (сначала новые, опциональный лимит)."""
    _user, _profile = current_user_data
    await ensure_nvd_sync_schema_compatibility()

    model = await get_active_translation_model_key(db)

    try:
        active_row = await get_latest_sync_log(db, active_only=True)
        if active_row:
            active_payload = sync_log_to_admin_payload(active_row)
            return AdminNvdSync(**active_payload)

        created_row = await create_translate_log(db)
    except ProgrammingError as exc:
        error_text = str(exc)
        if "nvd_sync_log" in error_text:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="nvd_sync_log table missing. Apply schema.sql changes.",
            ) from exc
        raise

    task = asyncio.create_task(run_translate_standalone_background(created_row["id"], limit=limit, model=model))
    _nvd_background_tasks.add(task)
    task.add_done_callback(_nvd_background_tasks.discard)
    created_payload = sync_log_to_admin_payload(created_row)
    return AdminNvdSync(**created_payload)


@router.post("/admin/nvd_sync/embed", response_model=AdminNvdSync, status_code=status.HTTP_202_ACCEPTED)
async def embed_nvd_entries(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Создать эмбеддинги для kb_entries без эмбеддингов (отдельно, в фоне)."""
    _user, _profile = current_user_data
    await ensure_nvd_sync_schema_compatibility()

    try:
        active_row = await get_latest_sync_log(db, active_only=True)
        if active_row:
            active_payload = sync_log_to_admin_payload(active_row)
            return AdminNvdSync(**active_payload)

        created_row = await create_embed_log(db)
    except ProgrammingError as exc:
        error_text = str(exc)
        if "nvd_sync_log" in error_text:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="nvd_sync_log table missing. Apply schema.sql changes.",
            ) from exc
        raise

    task = asyncio.create_task(run_embed_standalone_background(created_row["id"]))
    _nvd_background_tasks.add(task)
    task.add_done_callback(_nvd_background_tasks.discard)
    created_payload = sync_log_to_admin_payload(created_row)
    return AdminNvdSync(**created_payload)


@router.delete("/admin/nvd_sync/untranslated", response_model=dict)
async def purge_untranslated_entries(
    keep: int = Query(300, ge=0, le=10000),
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Удалить kb_entries без ru_summary, оставив `keep` самых новых строк."""
    _user, _profile = current_user_data
    result = await db.execute(
        text("""
            DELETE FROM kb_entries
            WHERE ru_summary IS NULL
              AND id NOT IN (
                  SELECT id FROM kb_entries
                  WHERE ru_summary IS NULL
                  ORDER BY id DESC
                  LIMIT :keep
              )
        """),
        {"keep": keep},
    )
    await db.commit()
    return {"deleted": result.rowcount}


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


@router.get("/admin/tasks/{task_id}", response_model=AdminTaskResponse)
async def get_admin_task(
    task_id: int,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    _user, _profile = current_user_data

    task = (await db.execute(select(Task).where(Task.id == task_id))).scalar_one_or_none()
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")

    flags = (
        await db.execute(select(TaskFlag).where(TaskFlag.task_id == task.id).order_by(TaskFlag.id.asc()))
    ).scalars().all()
    materials = (
        await db.execute(select(TaskMaterial).where(TaskMaterial.task_id == task.id).order_by(TaskMaterial.id.asc()))
    ).scalars().all()
    solution = (
        await db.execute(select(TaskAuthorSolution).where(TaskAuthorSolution.task_id == task.id))
    ).scalar_one_or_none()

    return _task_to_response(
        task,
        flags=flags,
        materials=materials,
        creation_solution=solution.creation_solution if solution else None,
    )


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
        prompt_text = await _resolve_prompt_text(db, "task_prompt")
        task_model_key = await get_active_task_model_key(db)
        folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
        task_model_uri = TASK_MODEL_REGISTRY[task_model_key](folder)
        result = await generate_task_payload_with_prompt(
            data.difficulty,
            tags,
            data.description,
            prompt_text,
            task_model_uri,
        )
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
    try:
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store generation log: {exc}",
        ) from exc

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
    access_type = _coerce_access_type(data.access_type)
    normalized_materials = _normalize_task_materials(data.materials)
    chat_prompt_text, chat_max_chars, chat_max_tokens, chat_ttl_minutes = _validate_chat_fields_or_400(
        access_type=access_type,
        chat_system_prompt_template=data.chat_system_prompt_template,
        chat_user_message_max_chars=data.chat_user_message_max_chars,
        chat_model_max_output_tokens=data.chat_model_max_output_tokens,
        chat_session_ttl_minutes=data.chat_session_ttl_minutes,
    )
    if access_type == "chat":
        flags_to_save = _build_chat_flags()
    else:
        if not data.flags or any(not (flag.expected_value or "").strip() for flag in data.flags):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="flags are required")
        normalized_flag_ids = [(flag.flag_id or "").strip() for flag in data.flags]
        if any(not flag_id for flag_id in normalized_flag_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="flag_id is required for each flag")
        if len(set(normalized_flag_ids)) != len(normalized_flag_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate flag_id in payload. Each flag_id must be unique per task.",
            )
        flags_to_save = [
            {
                "flag_id": (flag.flag_id or "").strip(),
                "format": (flag.format or "FLAG{...}").strip() or "FLAG{...}",
                "expected_value": (flag.expected_value or "").strip(),
                "description": flag.description,
            }
            for flag in data.flags
        ]
    if not data.title or not data.category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="title and category are required")

    try:
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
            parent_id=data.parent_id,
            access_type=access_type,
            chat_system_prompt_template=chat_prompt_text,
            chat_user_message_max_chars=chat_max_chars,
            chat_model_max_output_tokens=chat_max_tokens,
            chat_session_ttl_minutes=chat_ttl_minutes,
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

        for flag in flags_to_save:
            db.add(
                TaskFlag(
                    task_id=task.id,
                    flag_id=flag["flag_id"],
                    format=flag["format"],
                    expected_value=flag["expected_value"],
                    description=flag["description"],
                )
            )

        for material in normalized_materials:
            db.add(
                TaskMaterial(
                    task_id=task.id,
                    type=material["type"],
                    name=material["name"],
                    description=material["description"],
                    url=material["url"],
                    storage_key=material["storage_key"],
                    meta=material["meta"],
                )
            )

        await db.commit()
        await db.refresh(task)

        flags = (
            await db.execute(select(TaskFlag).where(TaskFlag.task_id == task.id))
        ).scalars().all()
        materials = (
            await db.execute(select(TaskMaterial).where(TaskMaterial.task_id == task.id).order_by(TaskMaterial.id.asc()))
        ).scalars().all()

        return _task_to_response(task, flags, materials, data.creation_solution)
    except IntegrityError as exc:
        await db.rollback()
        error_text = _format_db_error(exc)
        lowered = error_text.lower()
        if "task_flags" in lowered and "duplicate key" in lowered:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate flag_id in task flags. Each flag_id must be unique per task.",
            ) from exc
        if "foreign key" in lowered and "created_by" in lowered:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid creator user reference while saving task.",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task save integrity error: {error_text}",
        ) from exc
    except ProgrammingError as exc:
        await db.rollback()
        error_text = _format_db_error(exc)
        lowered = error_text.lower()
        schema_markers = ("does not exist", "undefined column", "relation", "column")
        if any(marker in lowered for marker in schema_markers):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Task save failed due to DB schema mismatch. Apply latest schema.sql changes. Raw DB error: {error_text}",
            ) from exc
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task save database error: {error_text}",
        ) from exc
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        logger.exception("Unexpected error while creating admin task")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task save failed: {exc}",
        ) from exc


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

    previous_access_type = _coerce_access_type(task.access_type)
    next_access_type = (
        _coerce_access_type(data.access_type)
        if data.access_type is not None
        else previous_access_type
    )

    resolved_chat_prompt = (
        data.chat_system_prompt_template
        if data.chat_system_prompt_template is not None
        else task.chat_system_prompt_template
    )
    resolved_chat_max_chars = (
        data.chat_user_message_max_chars
        if data.chat_user_message_max_chars is not None
        else task.chat_user_message_max_chars
    )
    resolved_chat_max_tokens = (
        data.chat_model_max_output_tokens
        if data.chat_model_max_output_tokens is not None
        else task.chat_model_max_output_tokens
    )
    resolved_chat_ttl_minutes = (
        data.chat_session_ttl_minutes
        if data.chat_session_ttl_minutes is not None
        else task.chat_session_ttl_minutes
    )
    chat_prompt_text, chat_max_chars, chat_max_tokens, chat_ttl_minutes = _validate_chat_fields_or_400(
        access_type=next_access_type,
        chat_system_prompt_template=resolved_chat_prompt,
        chat_user_message_max_chars=resolved_chat_max_chars,
        chat_model_max_output_tokens=resolved_chat_max_tokens,
        chat_session_ttl_minutes=resolved_chat_ttl_minutes,
    )

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
    if data.parent_id is not None:
        task.parent_id = data.parent_id
    task.access_type = next_access_type
    task.chat_system_prompt_template = chat_prompt_text
    task.chat_user_message_max_chars = chat_max_chars
    task.chat_model_max_output_tokens = chat_max_tokens
    task.chat_session_ttl_minutes = chat_ttl_minutes
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

    if next_access_type == "chat":
        await db.execute(delete(TaskFlag).where(TaskFlag.task_id == task.id))
        for flag in _build_chat_flags():
            db.add(
                TaskFlag(
                    task_id=task.id,
                    flag_id=flag["flag_id"],
                    format=flag["format"],
                    expected_value=flag["expected_value"],
                    description=flag["description"],
                )
            )
    elif data.flags is not None:
        normalized_flag_ids = [(flag.flag_id or "").strip() for flag in data.flags]
        if any(not flag_id for flag_id in normalized_flag_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="flag_id is required for each flag")
        if any(not (flag.expected_value or "").strip() for flag in data.flags):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="flags are required")
        if len(set(normalized_flag_ids)) != len(normalized_flag_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate flag_id in payload. Each flag_id must be unique per task.",
            )
        await db.execute(delete(TaskFlag).where(TaskFlag.task_id == task.id))
        for flag in data.flags:
            db.add(
                TaskFlag(
                    task_id=task.id,
                    flag_id=(flag.flag_id or "").strip(),
                    format=(flag.format or "FLAG{...}").strip() or "FLAG{...}",
                    expected_value=(flag.expected_value or "").strip(),
                    description=flag.description,
                )
            )
    elif previous_access_type == "chat" and next_access_type != "chat":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="flags are required when switching task from chat to non-chat access type",
        )

    if data.materials is not None:
        await db.execute(delete(TaskMaterial).where(TaskMaterial.task_id == task.id))
        normalized_materials = _normalize_task_materials(data.materials)
        for material in normalized_materials:
            db.add(
                TaskMaterial(
                    task_id=task.id,
                    type=material["type"],
                    name=material["name"],
                    description=material["description"],
                    url=material["url"],
                    storage_key=material["storage_key"],
                    meta=material["meta"],
                )
            )

    await db.commit()
    await db.refresh(task)

    flags = (
        await db.execute(select(TaskFlag).where(TaskFlag.task_id == task.id))
    ).scalars().all()
    materials = (
        await db.execute(select(TaskMaterial).where(TaskMaterial.task_id == task.id).order_by(TaskMaterial.id.asc()))
    ).scalars().all()
    solution = (
        await db.execute(
            select(TaskAuthorSolution).where(TaskAuthorSolution.task_id == task.id)
        )
    ).scalar_one_or_none()

    return _task_to_response(
        task,
        flags=flags,
        materials=materials,
        creation_solution=solution.creation_solution if solution else None,
    )


@router.delete("/admin/tasks/{task_id}")
async def delete_admin_task(
    task_id: int,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Удалить задачу и связанные сущности.
    """
    _user, _profile = current_user_data

    exists = (await db.execute(select(Task.id).where(Task.id == task_id))).scalar_one_or_none()
    if exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача не найдена")

    try:
        await db.execute(delete(ContestTask).where(ContestTask.task_id == task_id))
        await db.execute(delete(Submission).where(Submission.task_id == task_id))
        await db.execute(delete(TaskFlag).where(TaskFlag.task_id == task_id))
        await db.execute(delete(TaskMaterial).where(TaskMaterial.task_id == task_id))
        await db.execute(delete(TaskAuthorSolution).where(TaskAuthorSolution.task_id == task_id))
        await db.execute(
            update(LlmGeneration)
            .where(LlmGeneration.task_id == task_id)
            .values(task_id=None)
        )
        await db.execute(delete(Task).where(Task.id == task_id))
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось удалить задачу: {exc}",
        ) from exc

    return {"ok": True, "deleted_id": task_id}


@router.get("/admin/prompts", response_model=list[AdminPromptTemplate])
async def list_admin_prompts(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Список управляемых промптов для LLM.
    """
    _user, _profile = current_user_data

    overrides, _ = await _fetch_prompt_overrides(db)

    items: list[AdminPromptTemplate] = []
    for spec in PROMPT_SPECS:
        override = overrides.get(spec["code"])
        if override and (override.content or "").strip():
            content = override.content.strip()
            is_overridden = True
            updated_at = override.updated_at
        else:
            try:
                content = load_prompt_text(spec["filename"])
            except PromptLoadError:
                content = ""
            is_overridden = False
            updated_at = None

        items.append(
            AdminPromptTemplate(
                code=spec["code"],
                title=spec["title"],
                description=spec["description"],
                content=content,
                is_overridden=is_overridden,
                updated_at=updated_at,
            )
        )

    return items


@router.put("/admin/prompts/{code}", response_model=AdminPromptTemplate)
async def update_admin_prompt(
    code: str,
    data: AdminPromptUpdateRequest,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Обновить промпт в БД. Изменения применяются сразу к следующим генерациям.
    """
    user, _profile = current_user_data
    spec = PROMPT_SPEC_BY_CODE.get(code)
    if spec is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt not found")

    content = (data.content or "").strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content is required")

    try:
        row = (
            await db.execute(select(PromptTemplate).where(PromptTemplate.code == code))
        ).scalar_one_or_none()
    except ProgrammingError as exc:
        if "prompt_templates" in str(exc):
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="prompt_templates table missing. Apply schema.sql changes.",
            ) from exc
        raise

    if row is None:
        row = PromptTemplate(
            code=code,
            title=spec["title"],
            description=spec["description"],
            content=content,
            updated_by=user.id,
        )
        db.add(row)
    else:
        row.title = spec["title"]
        row.description = spec["description"]
        row.content = content
        row.updated_by = user.id
        row.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(row)

    return AdminPromptTemplate(
        code=row.code,
        title=row.title,
        description=row.description,
        content=row.content,
        is_overridden=True,
        updated_at=row.updated_at,
    )


@router.get("/admin/chat-model", response_model=AdminChatModelResponse)
async def get_admin_chat_model(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    _user, _profile = current_user_data
    active = await get_active_chat_model_key(db)
    return AdminChatModelResponse(model=active, available=list(CHAT_MODEL_REGISTRY.keys()))


@router.put("/admin/chat-model", response_model=AdminChatModelResponse)
async def set_admin_chat_model(
    data: AdminChatModelUpdate,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user, _profile = current_user_data
    model_key = (data.model or "").strip()
    if model_key not in CHAT_MODEL_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model. Available: {list(CHAT_MODEL_REGISTRY.keys())}",
        )

    try:
        row = (
            await db.execute(select(PromptTemplate).where(PromptTemplate.code == "chat_model"))
        ).scalar_one_or_none()
    except ProgrammingError as exc:
        if "prompt_templates" in str(exc):
            await db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="prompt_templates table missing. Apply schema.sql changes.",
            ) from exc
        raise

    if row is None:
        row = PromptTemplate(
            code="chat_model",
            title="Модель чата",
            description="Активная LLM-модель для чат-задач",
            content=model_key,
            updated_by=user.id,
        )
        db.add(row)
    else:
        row.content = model_key
        row.updated_by = user.id
        row.updated_at = datetime.now(timezone.utc)

    await db.commit()
    return AdminChatModelResponse(model=model_key, available=list(CHAT_MODEL_REGISTRY.keys()))


@router.get("/admin/task-model", response_model=AdminTaskModelResponse)
async def get_admin_task_model(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    _user, _profile = current_user_data
    active = await get_active_task_model_key(db)
    return AdminTaskModelResponse(model=active, available=list(TASK_MODEL_REGISTRY.keys()))


@router.put("/admin/task-model", response_model=AdminTaskModelResponse)
async def set_admin_task_model(
    data: AdminTaskModelUpdate,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user, _profile = current_user_data
    model_key = (data.model or "").strip()
    if model_key not in TASK_MODEL_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model. Available: {list(TASK_MODEL_REGISTRY.keys())}",
        )
    try:
        row = (
            await db.execute(select(PromptTemplate).where(PromptTemplate.code == "task_model"))
        ).scalar_one_or_none()
    except ProgrammingError as exc:
        if "prompt_templates" in str(exc):
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="prompt_templates table missing.") from exc
        raise
    if row is None:
        row = PromptTemplate(
            code="task_model",
            title="Модель генерации задач",
            description="Активная LLM-модель для генерации задач",
            content=model_key,
            updated_by=user.id,
        )
        db.add(row)
    else:
        row.content = model_key
        row.updated_by = user.id
        row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return AdminTaskModelResponse(model=model_key, available=list(TASK_MODEL_REGISTRY.keys()))


@router.get("/admin/translation-model", response_model=AdminTranslationModelResponse)
async def get_admin_translation_model(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    _user, _profile = current_user_data
    active = await get_active_translation_model_key(db)
    return AdminTranslationModelResponse(model=active, available=list(TRANSLATION_MODEL_REGISTRY.keys()))


@router.put("/admin/translation-model", response_model=AdminTranslationModelResponse)
async def set_admin_translation_model(
    data: AdminTranslationModelUpdate,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user, _profile = current_user_data
    model_key = (data.model or "").strip()
    if model_key not in TRANSLATION_MODEL_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model. Available: {list(TRANSLATION_MODEL_REGISTRY.keys())}",
        )
    try:
        row = (
            await db.execute(select(PromptTemplate).where(PromptTemplate.code == "translation_model"))
        ).scalar_one_or_none()
    except ProgrammingError as exc:
        if "prompt_templates" in str(exc):
            await db.rollback()
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="prompt_templates table missing.") from exc
        raise
    if row is None:
        row = PromptTemplate(
            code="translation_model",
            title="Модель перевода",
            description="Активная LLM-модель для перевода/обогащения CVE",
            content=model_key,
            updated_by=user.id,
        )
        db.add(row)
    else:
        row.content = model_key
        row.updated_by = user.id
        row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return AdminTranslationModelResponse(model=model_key, available=list(TRANSLATION_MODEL_REGISTRY.keys()))


@router.get("/admin/platform-model", response_model=AdminTaskModelResponse)
async def get_admin_platform_model(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    _user, _profile = current_user_data
    active = await get_active_task_model_key(db)
    return AdminTaskModelResponse(model=active, available=list(TASK_MODEL_REGISTRY.keys()))


@router.put("/admin/platform-model", response_model=AdminTaskModelResponse)
async def set_admin_platform_model(
    data: AdminTaskModelUpdate,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user, _profile = current_user_data
    model_key = (data.model or "").strip()
    if model_key not in TASK_MODEL_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model. Available: {list(TASK_MODEL_REGISTRY.keys())}",
        )
    for db_key, title, description in [
        ("task_model", "Модель генерации задач", "Активная LLM-модель для генерации задач"),
        ("translation_model", "Модель перевода", "Активная LLM-модель для перевода/обогащения CVE"),
    ]:
        try:
            row = (
                await db.execute(select(PromptTemplate).where(PromptTemplate.code == db_key))
            ).scalar_one_or_none()
        except ProgrammingError as exc:
            if "prompt_templates" in str(exc):
                await db.rollback()
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="prompt_templates table missing.") from exc
            raise
        if row is None:
            row = PromptTemplate(code=db_key, title=title, description=description, content=model_key, updated_by=user.id)
            db.add(row)
        else:
            row.content = model_key
            row.updated_by = user.id
            row.updated_at = datetime.now(timezone.utc)
    await db.commit()
    return AdminTaskModelResponse(model=model_key, available=list(TASK_MODEL_REGISTRY.keys()))


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
    if not (1 <= len(tasks) <= 10):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Контест должен иметь 1-10 задач")


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

    # Логируем активность
    user, _profile = current_user_data
    await log_contest_created(
        db=db,
        admin_id=user.id,
        contest_id=contest.id,
        contest_title=contest.title,
        details={"task_count": len(data.tasks)},
    )
    await db.commit()

    return await get_admin_contest(contest.id, current_user_data, db)


@router.post(
    "/admin/contests/{contest_id}/championship-tasks/generate",
    response_model=ChampionshipGenerateResponse,
)
async def generate_championship_tasks(
    contest_id: int,
    data: ChampionshipGenerateRequest,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    user, _profile = current_user_data

    contest = (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none()
    if contest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Контест не найден")

    if data.mode == "explicit" and not data.kb_entry_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="kb_entry_ids required for explicit mode")

    try:
        prompt_text = await _resolve_prompt_text(db, "championship_prompt")
    except HTTPException:
        try:
            from app.services.prompt_loader import load_prompt_text as _lpt
            prompt_text = _lpt("championship_prompt.txt")
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"championship_prompt.txt not found: {exc}",
            ) from exc

    task_model_key = data.model_key if (data.model_key and data.model_key in TASK_MODEL_REGISTRY) else await get_active_task_model_key(db)
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    model_uri = TASK_MODEL_REGISTRY[task_model_key](folder)

    try:
        clusters = await select_kb_entry_clusters(
            db,
            mode=data.mode,
            kb_entry_ids=data.kb_entry_ids,
            filters=data.filters.model_dump() if data.filters else None,
            count=data.count,
            k_per_task=3,
        )
    except ChampionshipGenerationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    existing_contest_tasks = (
        await db.execute(
            select(func.max(ContestTask.order_index)).where(ContestTask.contest_id == contest_id)
        )
    ).scalar()
    next_order_index = (existing_contest_tasks or -1) + 1

    created_ids: list[int] = []
    failed: list[dict] = []

    for cluster_idx, kb_entries in enumerate(clusters):
        try:
            result = await generate_championship_task(
                kb_entries=kb_entries,
                base_difficulty=data.base_difficulty,
                system_prompt=prompt_text,
                model_uri=model_uri,
            )
        except ChampionshipGenerationError as exc:
            failed.append({"cluster_index": cluster_idx, "error": str(exc)})
            continue

        try:
            task = await materialize_championship_task(
                db,
                result=result,
                base_difficulty=data.base_difficulty,
                created_by=user.id,
            )
            db.add(ContestTask(
                contest_id=contest_id,
                task_id=task.id,
                order_index=next_order_index + len(created_ids),
                points_override=None,
            ))
            await db.commit()
            created_ids.append(task.id)
        except Exception as exc:
            await db.rollback()
            failed.append({"cluster_index": cluster_idx, "error": str(exc)})

    return ChampionshipGenerateResponse(created=created_ids, failed=failed)


@router.post(
    "/admin/championship-tasks/generate",
    response_model=ChampionshipGenStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def start_championship_generation(
    data: ChampionshipGenerateRequest,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Запустить фоновый джоб для генерации отдельных (черновых) чемпионатных задач.

    Сразу возвращает job_id; фронтенд опрашивает GET .../jobs/{job_id} для отслеживания прогресса.
    """
    user, _profile = current_user_data

    if data.mode == "explicit" and not data.kb_entry_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="kb_entry_ids required for explicit mode")

    try:
        prompt_text = await _resolve_prompt_text(db, "championship_prompt")
    except HTTPException:
        from app.services.prompt_loader import load_prompt_text as _lpt
        prompt_text = _lpt("championship_prompt.txt")

    task_model_key = data.model_key if (data.model_key and data.model_key in TASK_MODEL_REGISTRY) else await get_active_task_model_key(db)
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    model_uri = TASK_MODEL_REGISTRY[task_model_key](folder)

    job = ContestGenJob(
        created_by=user.id,
        status="running",
        total=0,
        params={
            "mode": data.mode,
            "count": data.count,
            "base_difficulty": data.base_difficulty,
            "filters": data.filters.model_dump() if data.filters else None,
            "kb_entry_ids": data.kb_entry_ids,
        },
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    launch_generation_job(
        job_id=job.id,
        mode=data.mode,
        kb_entry_ids=data.kb_entry_ids,
        filters=data.filters.model_dump() if data.filters else None,
        count=data.count,
        base_difficulty=data.base_difficulty,
        system_prompt=prompt_text,
        model_uri=model_uri,
        admin_id=user.id,
    )

    return ChampionshipGenStartResponse(job_id=str(job.id), total=0)


@router.get(
    "/admin/championship-tasks/jobs/{job_id}",
    response_model=ChampionshipGenJobStatus,
)
async def get_championship_generation_job(
    job_id: str,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    job = await db.get(ContestGenJob, job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Задача генерации не найдена")
    return ChampionshipGenJobStatus(
        id=str(job.id),
        status=job.status,
        total=job.total or 0,
        completed=job.completed or 0,
        failed=job.failed or 0,
        events=job.events or [],
        created_task_ids=job.created_task_ids or [],
        error=job.error,
    )


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

    # Логируем активность
    user, _profile = current_user_data
    task_count = len(data.tasks) if data.tasks else 0
    await log_contest_updated(
        db=db,
        admin_id=user.id,
        contest_id=contest_id,
        contest_title=contest.title,
        details={"task_count": task_count} if data.tasks else None,
    )
    await db.commit()

    return await get_admin_contest(contest_id, current_user_data, db)


@router.post("/admin/contests/{contest_id}/end", response_model=AdminContestResponse)
async def end_admin_contest_now(
    contest_id: int,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Принудительно завершить контест текущим временем.
    """
    _user, _profile = current_user_data

    contest = (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none()
    if contest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Контест не найден")

    now = datetime.now(timezone.utc)

    # Сохраняем расписание консистентным для граничных случаев (например, будущий контест завершён вручную).
    if contest.start_at and contest.start_at > now:
        contest.start_at = now
    contest.end_at = now

    await db.commit()

    # Логируем активность
    user, _profile = current_user_data
    await log_contest_ended(
        db=db,
        admin_id=user.id,
        contest_id=contest_id,
        contest_title=contest.title,
    )
    await db.commit()

    return await get_admin_contest(contest_id, current_user_data, db)


@router.delete("/admin/contests/{contest_id}")
async def delete_admin_contest(
    contest_id: int,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Удалить контест и связанные сущности.
    """
    user, _profile = current_user_data

    contest = (await db.execute(select(Contest).where(Contest.id == contest_id))).scalar_one_or_none()
    if contest is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Контест не найден")

    contest_title = contest.title

    try:
        await db.execute(delete(ContestTask).where(ContestTask.contest_id == contest_id))
        await db.execute(delete(ContestParticipant).where(ContestParticipant.contest_id == contest_id))
        await db.execute(delete(Submission).where(Submission.contest_id == contest_id))
        await db.execute(delete(Contest).where(Contest.id == contest_id))
        await db.commit()
    except Exception as exc:  # noqa: BLE001
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Не удалось удалить контест: {exc}",
        ) from exc

    # Логируем активность
    await log_contest_deleted(
        db=db,
        admin_id=user.id,
        contest_id=contest_id,
        contest_title=contest_title,
    )
    await db.commit()

    return {"ok": True, "deleted_id": contest_id}


@router.get("/admin/activity-log", response_model=ActivityLogListResponse)
async def get_activity_log(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=500),
    event_type: Optional[str] = None,
    contest_id: Optional[int] = None,
    source: Optional[str] = None,
    search_text: Optional[str] = None,
):
    """
    Получить пагинированный лог активности с опциональными фильтрами.

    Query-параметры:
    - page: Номер страницы (по умолчанию 1)
    - page_size: Элементов на странице (по умолчанию 50, максимум 500)
    - event_type: Фильтр по типу события (например, "contest_created")
    - contest_id: Фильтр по ID контеста
    - source: Фильтр по источнику (admin_action, system_event, participant_action)
    - search_text: Поиск по полю action
    """
    _user, _profile = current_user_data

    offset = (page - 1) * page_size

    # Строим запрос
    query = select(ActivityLog)
    count_query = select(func.count()).select_from(ActivityLog)

    # Применяем фильтры
    if event_type:
        try:
            event_enum = EventType(event_type)
            query = query.where(ActivityLog.event_type == event_enum)
            count_query = count_query.where(ActivityLog.event_type == event_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Неверный event_type: {event_type}")

    if contest_id:
        query = query.where(ActivityLog.contest_id == contest_id)
        count_query = count_query.where(ActivityLog.contest_id == contest_id)

    if source:
        try:
            source_enum = EventSource(source)
            query = query.where(ActivityLog.source == source_enum)
            count_query = count_query.where(ActivityLog.source == source_enum)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Неверный source: {source}")

    if search_text:
        search_pattern = f"%{search_text}%"
        query = query.where(ActivityLog.action.ilike(search_pattern))
        count_query = count_query.where(ActivityLog.action.ilike(search_pattern))

    # Считаем общее количество
    total = (await db.execute(count_query)).scalar_one() or 0

    # Сортируем по created_at desc (сначала новые), затем пагинируем
    query = query.order_by(ActivityLog.created_at.desc()).offset(offset).limit(page_size)

    result = await db.execute(query)
    logs = result.scalars().all()

    return ActivityLogListResponse(
        items=[ActivityLogItemResponse.from_orm(log) for log in logs],
        total=total,
        page=page,
        page_size=page_size,
        has_more=(offset + page_size) < total,
    )


@router.get("/admin/pro_requests", response_model=list[ProRequestItem])
async def list_pro_requests(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """
    Список пользователей, подавших заявку на Pro подписку.
    Доступно только admin.
    """
    _user, _profile = current_user_data

    rows = (
        await db.execute(
            text(
                """
                SELECT p.user_id, p.username, u.email, u.created_at
                FROM user_profiles p
                JOIN users u ON u.id = p.user_id
                WHERE p.sub_request = TRUE
                ORDER BY u.created_at DESC
                """
            )
        )
    ).mappings().all()

    return [
        ProRequestItem(
            user_id=row["user_id"],
            username=row.get("username"),
            email=row.get("email"),
            created_at=row.get("created_at"),
        )
        for row in rows
    ]
