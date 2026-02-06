from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth.dependencies import get_current_user, get_current_admin
from app.database import get_db
from app.models.user import User, UserProfile
from app.schemas.admin import (
    AdminDashboardResponse,
    AdminStats,
    AdminFeedback,
    AdminChampionship,
    AdminArticle,
    AdminArticleCreateRequest,
    AdminNvdSync,
)
from app.services.nvd_sync import run_sync

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
                SELECT id, source, source_id, cve_id, ru_title, ru_summary, ru_explainer, created_at
                FROM kb_entries
                ORDER BY created_at DESC
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
                    (source, source_id, cve_id, raw_en_text, ru_title, ru_summary, ru_explainer, tags, difficulty)
                VALUES
                    (:source, :source_id, :cve_id, :raw_en_text, :ru_title, :ru_summary, :ru_explainer, :tags, :difficulty)
                RETURNING id, source, source_id, cve_id, raw_en_text, ru_title, ru_summary, ru_explainer, tags, difficulty, created_at
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
                SELECT id, source, source_id, cve_id, raw_en_text, ru_title, ru_summary, ru_explainer, tags, difficulty, created_at
                FROM kb_entries
                ORDER BY created_at DESC
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
                    difficulty = :difficulty
                WHERE id = :entry_id
                RETURNING id, source, source_id, cve_id, raw_en_text, ru_title, ru_summary, ru_explainer, tags, difficulty, created_at
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
