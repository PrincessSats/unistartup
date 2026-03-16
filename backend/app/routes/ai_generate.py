"""
AI Generator API routes — GRPO-based CTF challenge generation pipeline.

Endpoints:
  POST /ai-generate/                            — start generation batch (admin or PRO)
  GET  /ai-generate/batch/{batch_id}            — poll batch status + variant scores
  POST /ai-generate/batch/{batch_id}/publish/{variant_id} — admin: publish best variant as task
  GET  /ai-generate/analytics                   — admin: aggregated generation stats
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, func, cast, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_current_admin
from app.database import get_db
from app.models.ai_generation import (
    AIGenerationBatch,
    AIGenerationVariant,
    AIGenerationAnalytics,
)
from app.models.contest import Task, TaskFlag
from app.models.user import User, UserProfile
from app.schemas.ai_generation import (
    AnalyticsResponse,
    BatchStatusResponse,
    GenerateRequest,
    GenerateResponse,
    RewardCheckSchema,
    VariantSchema,
)
from app.services.ai_generator.pipeline import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(tags=["AI Generator"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require_admin_or_pro(user: User, profile: UserProfile) -> None:
    """Allow admin or users with PRO/CORP tariff."""
    if profile.role == "admin":
        return
    # For now only admin can generate; extend when tariff checks are needed
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Generating challenges requires admin access.",
    )


def _variant_to_schema(v: AIGenerationVariant) -> VariantSchema:
    checks = None
    if v.reward_checks:
        checks = [
            RewardCheckSchema(
                type=c.get("type", ""),
                score=c.get("score", 0.0),
                weight=c.get("weight", 1.0),
                detail=c.get("detail", ""),
                error=c.get("error"),
            )
            for c in v.reward_checks
        ]
    return VariantSchema(
        id=str(v.id),
        variant_number=v.variant_number,
        reward_total=v.reward_total,
        reward_binary=v.reward_binary,
        advantage=v.advantage,
        rank_in_group=v.rank_in_group,
        passed_all_binary=v.passed_all_binary or False,
        quality_score=v.quality_score,
        failure_reason=v.failure_reason,
        reward_checks=checks,
    )


async def _run_pipeline_bg(
    task_type: str,
    difficulty: str,
    num_variants: int,
    user_id: Optional[int],
    batch_id: uuid.UUID,
    cve_id: Optional[str] = None,
    topic: Optional[str] = None,
) -> None:
    """Background task wrapper — creates its own DB session."""
    import traceback
    print(f"[PIPELINE] background task started batch={batch_id}", flush=True)
    from app.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            print(f"[PIPELINE] DB session opened, calling run_pipeline", flush=True)
            await run_pipeline(
                task_type=task_type,
                difficulty=difficulty,
                num_variants=num_variants,
                user_id=user_id,
                batch_id=batch_id,
                db=db,
                cve_id=cve_id,
                topic=topic,
            )
            print(f"[PIPELINE] run_pipeline returned OK", flush=True)
        except Exception:
            print(f"[PIPELINE] CRASHED:\n{traceback.format_exc()}", flush=True)
            logger.exception("Pipeline background task crashed for batch=%s", batch_id)
            try:
                from sqlalchemy import select
                from datetime import datetime, timezone
                result = await db.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == batch_id))
                batch = result.scalar_one_or_none()
                if batch and batch.status not in ("completed", "failed"):
                    batch.status = "failed"
                    batch.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                pass


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ai-generate/", response_model=GenerateResponse, status_code=status.HTTP_202_ACCEPTED)
async def start_generation(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> GenerateResponse:
    """Start a new AI generation batch. Returns batch_id immediately; poll for status."""
    user, profile = current_user_data
    _require_admin_or_pro(user, profile)

    batch_id = uuid.uuid4()
    batch = AIGenerationBatch(
        id=batch_id,
        requested_by=user.id,
        task_type=request.task_type,
        difficulty=request.difficulty,
        num_variants=request.num_variants,
        status="pending",
    )
    db.add(batch)
    await db.commit()

    background_tasks.add_task(
        _run_pipeline_bg,
        request.task_type,
        request.difficulty,
        request.num_variants,
        user.id,
        batch_id,
        request.cve_id,
        request.topic,
    )

    logger.info("Started generation batch=%s type=%s difficulty=%s", batch_id, request.task_type, request.difficulty)
    return GenerateResponse(batch_id=str(batch_id), status="generating")


@router.get("/ai-generate/batch/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BatchStatusResponse:
    """Poll batch status and variant scores. Does not expose generated_spec."""
    user, profile = current_user_data

    try:
        bid = uuid.UUID(batch_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid batch_id format")

    result = await db.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == bid))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    # Non-admins can only view their own batches
    if profile.role != "admin" and batch.requested_by != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")

    variants_result = await db.execute(
        select(AIGenerationVariant)
        .where(AIGenerationVariant.batch_id == bid)
        .order_by(AIGenerationVariant.variant_number)
    )
    variants = variants_result.scalars().all()

    return BatchStatusResponse(
        batch_id=str(batch.id),
        status=batch.status,
        task_type=batch.task_type,
        difficulty=batch.difficulty,
        attempt=batch.attempt,
        group_mean_reward=batch.group_mean_reward,
        group_std_reward=batch.group_std_reward,
        pass_rate=batch.pass_rate,
        variants=[_variant_to_schema(v) for v in variants],
        selected_variant_id=str(batch.selected_variant_id) if batch.selected_variant_id else None,
        rag_context_ids=batch.rag_context_ids,
        rag_query_text=batch.rag_query_text,
    )


@router.post("/ai-generate/batch/{batch_id}/publish/{variant_id}", status_code=status.HTTP_201_CREATED)
async def publish_variant(
    batch_id: str,
    variant_id: str,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Admin only: publish the selected variant as a live CTF task."""
    user, profile = current_user_data

    try:
        bid = uuid.UUID(batch_id)
        vid = uuid.UUID(variant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")

    # Load variant
    variant_result = await db.execute(
        select(AIGenerationVariant).where(
            AIGenerationVariant.id == vid,
            AIGenerationVariant.batch_id == bid,
        )
    )
    variant = variant_result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    if variant.published_task_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Variant already published")

    if not variant.passed_all_binary:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot publish a variant that failed binary checks",
        )

    spec = variant.generated_spec or {}

    # Map task_type to access_type
    batch_result = await db.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == bid))
    batch = batch_result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    access_type_map = {
        "crypto_text_web": "just_flag",
        "forensics_image_metadata": "file",
        "web_static_xss": "link",
        "chat_llm": "chat",
    }
    access_type = access_type_map.get(batch.task_type, "just_flag")

    # Determine access_data (file URL or page URL for non-crypto types)
    artifact = variant.artifact_result or {}
    access_data = artifact.get("file_url") or artifact.get("content") or None

    # Create the task
    difficulty_to_points = {"beginner": 50, "intermediate": 100, "advanced": 200}
    task = Task(
        title=spec.get("title", f"AI Generated — {batch.task_type}"),
        category=batch.task_type.split("_")[0].capitalize(),
        difficulty={"beginner": 1, "intermediate": 2, "advanced": 3}.get(batch.difficulty, 1),
        points=difficulty_to_points.get(batch.difficulty, 100),
        access_type=access_type,
        story=spec.get("description"),
        participant_description=spec.get("description"),
        created_by=user.id,
    )
    db.add(task)
    await db.flush()  # get task.id

    # Create task flag
    flag_value = spec.get("flag", "")
    if flag_value:
        db.add(TaskFlag(
            task_id=task.id,
            flag_id="main",
            format="static",
            expected_value=flag_value,
            description="Auto-generated flag",
        ))

    # Mark variant as published
    variant.is_selected = True
    variant.published_task_id = task.id

    # Update batch
    batch.selected_variant_id = variant.id

    await db.commit()

    # Embed the published task for future duplicate detection (non-critical)
    try:
        from app.services.ai_generator.embedding_service import EmbeddingService, EmbeddingError
        embed_text = " ".join(filter(None, [
            spec.get("title", ""),
            spec.get("description", ""),
        ]))
        if embed_text.strip():
            svc = EmbeddingService()
            try:
                embedding = await svc.embed_document(embed_text)
                task.embedding = embedding
                await db.commit()
            finally:
                await svc.close()
    except Exception as exc:
        logger.warning("Failed to embed published task=%s: %s", task.id, exc)

    logger.info("Published variant=%s as task=%s", variant_id, task.id)
    return {"task_id": task.id, "variant_id": variant_id, "status": "published"}


@router.get("/ai-generate/analytics", response_model=list[AnalyticsResponse])
async def get_analytics(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AnalyticsResponse]:
    """Admin only: aggregated generation stats per task_type and difficulty."""
    result = await db.execute(
        select(AIGenerationAnalytics).order_by(
            AIGenerationAnalytics.task_type,
            AIGenerationAnalytics.difficulty,
            AIGenerationAnalytics.period_date.desc(),
        )
    )
    rows = result.scalars().all()

    return [
        AnalyticsResponse(
            task_type=row.task_type,
            difficulty=row.difficulty,
            total_variants=row.total_variants or 0,
            passed_variants=row.passed_variants or 0,
            pass_rate=(row.passed_variants or 0) / max(row.total_variants or 1, 1),
            avg_quality_score=row.avg_quality_score,
            common_failures=row.common_failures or [],
            best_temperature=row.best_temperature,
        )
        for row in rows
    ]
