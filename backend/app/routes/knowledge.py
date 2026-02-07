from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import Text, bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.database import get_db
from app.schemas.comments import KBComment, KBCommentCreate
from app.schemas.knowledge import KnowledgeEntry
from app.security.rate_limit import RateLimit, enforce_rate_limit

router = APIRouter(prefix="/kb_entries", tags=["Knowledge Base"])


@router.get("", response_model=List[KnowledgeEntry])
async def list_kb_entries(
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(12, ge=1, le=50),
    offset: int = Query(0, ge=0),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    tag: Optional[str] = Query(None),
    only_with_title: bool = Query(False),
):
    """
    Список записей базы знаний.
    order: asc | desc (по created_at)
    tag: фильтр по тегу (если указан)
    """
    _user, _profile = current_user_data

    order_sql = "ASC" if order == "asc" else "DESC"
    tag_value = tag.strip() if isinstance(tag, str) and tag.strip() else None

    stmt = text(
        f"""
        SELECT id, source, source_id, cve_id, ru_title, ru_summary, ru_explainer, tags, difficulty, created_at, updated_at
        FROM kb_entries
        WHERE (:tag IS NULL OR :tag = ANY(tags))
          AND (:only_with_title IS FALSE OR (ru_title IS NOT NULL AND length(trim(ru_title)) > 0))
        ORDER BY COALESCE(updated_at, created_at) {order_sql}
        LIMIT :limit
        OFFSET :offset
        """
    ).bindparams(bindparam("tag", type_=Text))

    rows = (
        await db.execute(
            stmt,
            {
                "limit": limit,
                "offset": offset,
                "tag": tag_value,
                "only_with_title": only_with_title,
            },
        )
    ).mappings().all()

    return [
        KnowledgeEntry(
            id=row["id"],
            source=row["source"],
            source_id=row.get("source_id"),
            cve_id=row.get("cve_id"),
            ru_title=row.get("ru_title"),
            ru_summary=row.get("ru_summary"),
            ru_explainer=row.get("ru_explainer"),
            tags=row.get("tags") or [],
            difficulty=row.get("difficulty"),
            created_at=row["created_at"],
            updated_at=row.get("updated_at"),
        )
        for row in rows
    ]


@router.get("/paged")
async def list_kb_entries_paged(
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(15, ge=1, le=50),
    offset: int = Query(0, ge=0),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    tag: Optional[str] = Query(None),
    only_with_title: bool = Query(True),
):
    """
    Пагинация для базы знаний (с total).
    """
    _user, _profile = current_user_data

    order_sql = "ASC" if order == "asc" else "DESC"
    tag_value = tag.strip() if isinstance(tag, str) and tag.strip() else None

    count_stmt = text(
        """
        SELECT COUNT(*)
        FROM kb_entries
        WHERE (:tag IS NULL OR :tag = ANY(tags))
          AND (:only_with_title IS FALSE OR (ru_title IS NOT NULL AND length(trim(ru_title)) > 0))
        """
    ).bindparams(bindparam("tag", type_=Text))

    total = (
        await db.execute(
            count_stmt,
            {"tag": tag_value, "only_with_title": only_with_title},
        )
    ).scalar_one() or 0

    rows = (
        await db.execute(
            text(
                f"""
                SELECT id, source, source_id, cve_id, ru_title, ru_summary, ru_explainer, tags, difficulty, created_at, updated_at
                FROM kb_entries
                WHERE (:tag IS NULL OR :tag = ANY(tags))
                  AND (:only_with_title IS FALSE OR (ru_title IS NOT NULL AND length(trim(ru_title)) > 0))
                ORDER BY COALESCE(updated_at, created_at) {order_sql}
                LIMIT :limit
                OFFSET :offset
                """
            ).bindparams(bindparam("tag", type_=Text)),
            {"limit": limit, "offset": offset, "tag": tag_value, "only_with_title": only_with_title},
        )
    ).mappings().all()

    items = [
        KnowledgeEntry(
            id=row["id"],
            source=row["source"],
            source_id=row.get("source_id"),
            cve_id=row.get("cve_id"),
            ru_title=row.get("ru_title"),
            ru_summary=row.get("ru_summary"),
            ru_explainer=row.get("ru_explainer"),
            tags=row.get("tags") or [],
            difficulty=row.get("difficulty"),
            created_at=row["created_at"],
            updated_at=row.get("updated_at"),
        )
        for row in rows
    ]

    return {
        "items": items,
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/tags")
async def list_kb_tags(
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    only_with_title: bool = Query(True),
):
    """
    Список всех тегов.
    """
    _user, _profile = current_user_data

    rows = (
        await db.execute(
            text(
                """
                SELECT DISTINCT unnest(tags) AS tag
                FROM kb_entries
                WHERE tags IS NOT NULL
                  AND (:only_with_title IS FALSE OR (ru_title IS NOT NULL AND length(trim(ru_title)) > 0))
                ORDER BY tag ASC
                """
            ),
            {"only_with_title": only_with_title},
        )
    ).mappings().all()

    return [row["tag"] for row in rows if row.get("tag")]


@router.get("/{entry_id}", response_model=KnowledgeEntry)
async def get_kb_entry(
    entry_id: int,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Получить одну запись базы знаний по id.
    """
    _user, _profile = current_user_data

    stmt = text(
        """
        SELECT id, source, source_id, cve_id, ru_title, ru_summary, ru_explainer, tags, difficulty, created_at, updated_at
        FROM kb_entries
        WHERE id = :entry_id
        """
    )

    row = (
        await db.execute(
            stmt,
            {
                "entry_id": entry_id,
            },
        )
    ).mappings().first()

    if not row:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    return KnowledgeEntry(
        id=row["id"],
        source=row["source"],
        source_id=row.get("source_id"),
        cve_id=row.get("cve_id"),
        ru_title=row.get("ru_title"),
        ru_summary=row.get("ru_summary"),
        ru_explainer=row.get("ru_explainer"),
        tags=row.get("tags") or [],
        difficulty=row.get("difficulty"),
        created_at=row["created_at"],
        updated_at=row.get("updated_at"),
    )


@router.get("/{entry_id}/comments", response_model=List[KBComment])
async def list_kb_comments(
    entry_id: int,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """
    Список комментариев к статье.
    """
    _user, _profile = current_user_data

    entry_row = (
        await db.execute(
            text(
                """
                SELECT id
                FROM kb_entries
                WHERE id = :entry_id
                """
            ),
            {"entry_id": entry_id},
        )
    ).mappings().first()

    if not entry_row:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    rows = (
        await db.execute(
            text(
                """
                SELECT c.id,
                       c.kb_entry_id,
                       c.user_id,
                       c.parent_id,
                       c.body,
                       c.status,
                       c.created_at,
                       p.username,
                       p.avatar_url
                FROM kb_comments c
                LEFT JOIN user_profiles p ON p.user_id = c.user_id
                WHERE c.kb_entry_id = :entry_id
                  AND c.status = 'published'
                ORDER BY c.created_at DESC
                LIMIT :limit
                OFFSET :offset
                """
            ),
            {"entry_id": entry_id, "limit": limit, "offset": offset},
        )
    ).mappings().all()

    return [
        KBComment(
            id=row["id"],
            kb_entry_id=row["kb_entry_id"],
            user_id=row["user_id"],
            parent_id=row.get("parent_id"),
            body=row["body"],
            status=row["status"],
            created_at=row["created_at"],
            username=row.get("username"),
            avatar_url=row.get("avatar_url"),
        )
        for row in rows
    ]


@router.post("/{entry_id}/comments", response_model=KBComment, status_code=status.HTTP_201_CREATED)
async def create_kb_comment(
    request: Request,
    entry_id: int,
    data: KBCommentCreate,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Создать комментарий к статье.
    """
    user, _profile = current_user_data
    enforce_rate_limit(
        request,
        scope="kb_comment_create",
        subject=f"{user.id}:{entry_id}",
        rule=RateLimit(max_requests=20, window_seconds=60),
    )

    body = (data.body or "").strip()
    if not body:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Комментарий не может быть пустым",
        )

    if len(body) > 2000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Комментарий слишком длинный",
        )

    entry_row = (
        await db.execute(
            text(
                """
                SELECT id
                FROM kb_entries
                WHERE id = :entry_id
                """
            ),
            {"entry_id": entry_id},
        )
    ).mappings().first()

    if not entry_row:
        raise HTTPException(status_code=404, detail="Статья не найдена")

    parent_id = data.parent_id
    if parent_id is not None:
        parent_row = (
            await db.execute(
                text(
                    """
                    SELECT id, kb_entry_id
                    FROM kb_comments
                    WHERE id = :parent_id
                    """
                ),
                {"parent_id": parent_id},
            )
        ).mappings().first()

        if not parent_row or parent_row["kb_entry_id"] != entry_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некорректный parent_id",
            )

    row = (
        await db.execute(
            text(
                """
                INSERT INTO kb_comments (kb_entry_id, user_id, parent_id, body, status)
                VALUES (:entry_id, :user_id, :parent_id, :body, 'published')
                RETURNING id, kb_entry_id, user_id, parent_id, body, status, created_at
                """
            ),
            {
                "entry_id": entry_id,
                "user_id": user.id,
                "parent_id": parent_id,
                "body": body,
            },
        )
    ).mappings().first()

    await db.commit()

    profile_row = (
        await db.execute(
            text(
                """
                SELECT username, avatar_url
                FROM user_profiles
                WHERE user_id = :user_id
                """
            ),
            {"user_id": user.id},
        )
    ).mappings().first()

    return KBComment(
        id=row["id"],
        kb_entry_id=row["kb_entry_id"],
        user_id=row["user_id"],
        parent_id=row.get("parent_id"),
        body=row["body"],
        status=row["status"],
        created_at=row["created_at"],
        username=profile_row.get("username") if profile_row else None,
        avatar_url=profile_row.get("avatar_url") if profile_row else None,
    )
