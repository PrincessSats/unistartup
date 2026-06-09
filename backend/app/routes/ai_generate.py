"""
Маршруты API генератора на базе GRPO для создания CTF-заданий.

Эндпоинты:
  POST /ai-generate/                            — запустить пакет генерации (админ или PRO)
  GET  /ai-generate/batch/{batch_id}            — опросить статус пакета + оценки вариантов
  POST /ai-generate/batch/{batch_id}/publish/{variant_id} — админ: опубликовать лучший вариант как задание
  GET  /ai-generate/analytics                   — админ: агрегированная статистика генерации
"""
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, func, cast, Date
from sqlalchemy.orm import joinedload
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user, get_current_admin
from app.database import get_db
from app.models.ai_generation import (
    AIGenerationBatch,
    AIGenerationVariant,
    AIGenerationAnalytics,
)
from app.models.user_task_variant import UserTaskVariantRequest
from app.models.contest import Task, TaskFlag, TaskMaterial, TaskAuthorSolution
from app.models.user import User, UserProfile
from app.schemas.ai_generation import (
    AnalyticsResponse,
    BatchStatusResponse,
    GenerateRequest,
    GenerateResponse,
    RewardCheckSchema,
    VariantReviewSchema,
    VariantSchema,
)
from app.services.ai_generator.pipeline import run_pipeline

logger = logging.getLogger(__name__)
router = APIRouter(tags=["AI Generator"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _require_admin_or_pro(user: User, profile: UserProfile) -> None:
    """Разрешить админу или пользователям с PRO/CORP тарифом."""
    if profile.role == "admin":
        return
    # Пока только админ может генерировать; расширить когда нужны проверки тарифа
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
    # Извлекаем безопасные поля из spec (никогда не раскрываем flag)
    spec = v.generated_spec or {}
    spec_title = spec.get("title") if spec else None
    spec_description = spec.get("description") if spec else None
    # Извлекаем содержимое артефакта (только зашифрованный текст, без verification_data)
    artifact = v.artifact_result or {}
    artifact_content = artifact.get("content") if artifact else None
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
        temperature=v.temperature,
        model_used=v.model_used,
        tokens_input=v.tokens_input,
        tokens_output=v.tokens_output,
        generation_time_ms=v.generation_time_ms,
        quality_details=v.quality_details,
        spec_title=spec_title,
        spec_description=spec_description,
        artifact_content=artifact_content,
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
    """Обёртка фоновой задачи — создаёт собственную сессию БД."""
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
    """Запускает новый пакет AI-генерации. Сразу возвращает batch_id; статус можно опрашивать."""
    user, profile = current_user_data
    _require_admin_or_pro(user, profile)

    # Определяем task_type из CVE CWE данных когда не указано явно
    task_type = request.task_type
    if task_type is None:
        if request.cve_id:
            from app.services.ai_generator.cwe_mapping import infer_task_type
            from sqlalchemy import text as sa_text
            cwe_result = await db.execute(sa_text(
                "SELECT cwe_ids, attack_vector FROM kb_entries WHERE cve_id = :cve_id LIMIT 1"
            ), {"cve_id": request.cve_id})
            cwe_row = cwe_result.fetchone()
            cwe_ids = list(cwe_row[0] or []) if cwe_row else []
            attack_vector = cwe_row[1] if cwe_row else None
            task_type = infer_task_type(cwe_ids, attack_vector)
        else:
            task_type = "crypto_text_web"  # default fallback

    batch_id = uuid.uuid4()
    batch = AIGenerationBatch(
        id=batch_id,
        requested_by=user.id,
        task_type=task_type,
        difficulty=request.difficulty,
        num_variants=request.num_variants,
        status="pending",
    )
    db.add(batch)
    await db.commit()

    background_tasks.add_task(
        _run_pipeline_bg,
        task_type,
        request.difficulty,
        request.num_variants,
        user.id,
        batch_id,
        request.cve_id,
        request.topic,
    )

    logger.info("Started generation batch=%s type=%s difficulty=%s", batch_id, task_type, request.difficulty)
    return GenerateResponse(batch_id=str(batch_id), status="generating", task_type=task_type)


@router.get("/ai-generate/batch/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    current_user_data: tuple = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BatchStatusResponse:
    """Опрашивает статус пакета и оценки вариантов. generated_spec не раскрывается."""
    user, profile = current_user_data

    try:
        bid = uuid.UUID(batch_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid batch_id format")

    result = await db.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == bid))
    batch = result.scalar_one_or_none()
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Batch not found")

    # Не-админы могут видеть только свои batches
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
        current_stage=batch.current_stage,
        stage_started_at=batch.stage_started_at.isoformat() if batch.stage_started_at else None,
        stage_meta=batch.stage_meta,
        created_at=batch.created_at.isoformat() if batch.created_at else None,
        num_variants=batch.num_variants,
    )


@router.get("/ai-generate/batch/{batch_id}/variant/{variant_id}/review", response_model=VariantReviewSchema)
async def get_variant_review(
    batch_id: str,
    variant_id: str,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> VariantReviewSchema:
    """Только для админа: полный просмотр варианта, включая флаг и данные верификации, перед публикацией."""
    try:
        bid = uuid.UUID(batch_id)
        vid = uuid.UUID(variant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")

    result = await db.execute(
        select(AIGenerationVariant).where(
            AIGenerationVariant.id == vid,
            AIGenerationVariant.batch_id == bid,
        )
    )
    variant = result.scalar_one_or_none()
    if not variant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    spec = variant.generated_spec or {}
    artifact = variant.artifact_result or {}

    checks = None
    if variant.reward_checks:
        checks = [
            RewardCheckSchema(
                type=c.get("type", ""),
                score=c.get("score", 0.0),
                weight=c.get("weight", 1.0),
                detail=c.get("detail", ""),
                error=c.get("error"),
            )
            for c in variant.reward_checks
        ]

    return VariantReviewSchema(
        id=str(variant.id),
        variant_number=variant.variant_number,
        spec_title=spec.get("title"),
        spec_description=spec.get("description"),
        spec_story=spec.get("story") or spec.get("participant_description"),
        spec_flag=spec.get("flag"),
        spec_hint=spec.get("hint"),
        spec_category=spec.get("category"),
        spec_raw=spec if spec else None,  # full spec including flag — admin-only endpoint
        artifact_content=artifact.get("content"),
        artifact_file_url=artifact.get("file_url"),
        artifact_verification=artifact.get("verification_data"),
        artifact_error=artifact.get("error"),
        temperature=variant.temperature,
        model_used=variant.model_used,
        tokens_input=variant.tokens_input,
        tokens_output=variant.tokens_output,
        generation_time_ms=variant.generation_time_ms,
        reward_total=variant.reward_total,
        reward_binary=variant.reward_binary,
        quality_score=variant.quality_score,
        quality_details=variant.quality_details,
        advantage=variant.advantage,
        rank_in_group=variant.rank_in_group,
        passed_all_binary=variant.passed_all_binary or False,
        failure_reason=variant.failure_reason,
        reward_checks=checks,
        is_selected=variant.is_selected or False,
        published_task_id=variant.published_task_id,
    )


@router.post("/ai-generate/batch/{batch_id}/publish/{variant_id}", status_code=status.HTTP_201_CREATED)
async def publish_variant(
    batch_id: str,
    variant_id: str,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Только для админа: публикует выбранный вариант как активное CTF-задание."""
    user, profile = current_user_data

    try:
        bid = uuid.UUID(batch_id)
        vid = uuid.UUID(variant_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid UUID format")

    # Загружаем вариант с user_variant_request relationship
    variant_result = await db.execute(
        select(AIGenerationVariant)
        .options(joinedload(AIGenerationVariant.user_variant_request))
        .where(
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

    # Маппируем task_type в access_type
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

    artifact = variant.artifact_result or {}
    ciphertext = artifact.get("content")
    file_url = artifact.get("file_url")
    verification_data = artifact.get("verification_data") or {}

    # Строим participant_description: базовое описание + зашифрованный текст если присутствует
    # Для chat задач artifact содержит system prompt — не добавляем к participant_desc
    base_desc = spec.get("description") or spec.get("participant_description") or ""
    is_chat = access_type == "chat"
    if not is_chat and ciphertext and ciphertext not in base_desc:
        participant_desc = f"{base_desc}\n\nCiphertext (what you need to decode):\n```\n{ciphertext}\n```" if base_desc else f"Ciphertext (what you need to decode):\n```\n{ciphertext}\n```"
    else:
        participant_desc = base_desc

    # Отклоняем дублирующиеся названия задач
    title = spec.get("title", f"AI Generated — {batch.task_type}")
    dup = await db.execute(select(Task.id).where(Task.title == title))
    if dup.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Task '{title}' already exists",
        )

    # Создаем задачу
    difficulty_to_points = {"beginner": 50, "intermediate": 100, "advanced": 200}

    # Проверяем это ли user variant request (relationship уже загружена)
    is_user_variant = variant.user_variant_request is not None

    # Для chat задач подбираем опциональные переопределения limit из spec
    chat_extras: dict = {}
    if is_chat:
        chat_extras["chat_system_prompt_template"] = ciphertext or ""
        for field in ("chat_user_message_max_chars", "chat_model_max_output_tokens", "chat_session_ttl_minutes"):
            raw = spec.get(field)
            if raw is not None:
                try:
                    chat_extras[field] = int(raw)
                except (TypeError, ValueError):
                    pass

    task = Task(
        title=spec.get("title", f"AI Generated — {batch.task_type}"),
        category=batch.task_type.split("_")[0].capitalize(),
        task_kind="ugc" if is_user_variant else "practice",
        difficulty={"beginner": 1, "intermediate": 2, "advanced": 3}.get(batch.difficulty, 1),
        points=difficulty_to_points.get(batch.difficulty, 100),
        access_type=access_type,
        story=spec.get("story") or spec.get("description"),
        participant_description=participant_desc,
        kb_entry_id=(batch.rag_context_ids[0] if batch.rag_context_ids else None),
        llm_raw_response=spec,  # full spec stored for admin reference
        created_by=user.id,
        **chat_extras,
    )

    # Если вариант связан с user request установляем parent_id
    if is_user_variant:
        task.parent_id = variant.user_variant_request.parent_task_id

    db.add(task)
    await db.flush()  # get task.id

    # Создаем task flag — пропускаем для chat задач (флаги динамичны в сессии)
    flag_value = spec.get("flag", "")
    if flag_value and not is_chat:
        db.add(TaskFlag(
            task_id=task.id,
            flag_id="main",
            format="static",
            expected_value=flag_value,
            description="Auto-generated flag",
        ))

    # Сохраняем артефакт как TaskMaterial чтобы он всегда был доступен
    if ciphertext or file_url:
        crypto_chain = verification_data.get("chain") or spec.get("crypto_chain")
        mat_kwargs: dict = dict(
            task_id=task.id,
            type="artifact",
            name="Generated artifact",
            description=f"Auto-generated artifact for {batch.task_type}",
            url=file_url,
            meta={
                "content": ciphertext,
                "crypto_chain": crypto_chain,
                "task_type": batch.task_type,
            },
        )
        # Для файловых артефактов устанавливаем storage_key чтобы presigned-URL работал
        if file_url and batch.task_type == "forensics_image_metadata":
            mat_kwargs["name"] = "Forensics image"
            mat_kwargs["storage_key"] = file_url
        db.add(TaskMaterial(**mat_kwargs))

    # Сохраняем решение автора (шаги разворачивания цепи шифрования)
    crypto_chain = verification_data.get("chain") or spec.get("crypto_chain")
    if crypto_chain:
        reversed_steps = [
            {"step": i + 1, "cipher": op.get("cipher"), "params": op.get("params", {}), "direction": "reverse"}
            for i, op in enumerate(reversed(crypto_chain))
        ]
        forward_steps = [
            {"step": i + 1, "cipher": op.get("cipher"), "params": op.get("params", {}), "direction": "encrypt"}
            for i, op in enumerate(crypto_chain)
        ]
        chain_summary = " → ".join(op.get("cipher", "?") for op in crypto_chain)
        db.add(TaskAuthorSolution(
            task_id=task.id,
            summary=f"Reverse the encryption chain: {chain_summary}",
            creation_solution=f"Flag was encrypted with: {chain_summary}\nTo solve: apply inverse operations in reverse order.",
            steps={"encrypt": forward_steps, "decrypt": reversed_steps},
        ))

    # Сохраняем решение автора для forensics
    if batch.task_type == "forensics_image_metadata":
        hide_in = spec.get("hide_in", "unknown")
        db.add(TaskAuthorSolution(
            task_id=task.id,
            summary=f"Flag hidden in: {hide_in}",
            creation_solution=spec.get("writeup", ""),
            steps={"hide_in": hide_in, "decoy_metadata": spec.get("decoy_metadata", {})},
        ))

    # Сохраняем решение автора для XSS
    if batch.task_type == "web_static_xss":
        # Также сохраняем file_url как TaskMaterial storage_key для скачивания
        if file_url:
            # Обновляем уже добавленный TaskMaterial с storage_key
            mat_kwargs["name"] = "XSS challenge page"
            mat_kwargs["storage_key"] = file_url
        xss_type = spec.get("xss_type", "reflected")
        param = spec.get("vulnerable_param", "")
        db.add(TaskAuthorSolution(
            task_id=task.id,
            summary=f"XSS ({xss_type}) via parameter: {param}",
            creation_solution=spec.get("writeup", ""),
            steps={
                "xss_type": xss_type,
                "vulnerable_param": param,
                "payload_solution": spec.get("payload_solution", ""),
                "filter_bypass": spec.get("filter_bypass", ""),
            },
        ))

    # Конфигурируем chat_llm задачу
    if batch.task_type == "chat_llm":
        system_prompt_template = artifact.get("content") or spec.get("system_prompt_template", "")
        if system_prompt_template:
            task.chat_system_prompt_template = system_prompt_template
        db.add(TaskAuthorSolution(
            task_id=task.id,
            summary=f"Prompt injection: {spec.get('attack_hint', 'jailbreak')}",
            creation_solution=spec.get("writeup", ""),
            steps={
                "defense_type": spec.get("defense_type", ""),
                "attack_hint": spec.get("attack_hint", ""),
                "system_prompt_template": system_prompt_template,
            },
        ))

    # Отмечаем вариант как опубликованный
    variant.is_selected = True
    variant.published_task_id = task.id

    # Обновляем batch
    batch.selected_variant_id = variant.id

    await db.commit()

    # Встраиваем опубликованную задачу для обнаружения дубликатов в будущем (не критично)
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


@router.get("/ai-generate/batches")
async def list_batches(
    status: Optional[str] = None,
    task_type: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Только для админа: постраничный список пакетов генерации."""
    query = select(AIGenerationBatch).order_by(AIGenerationBatch.created_at.desc())
    if status:
        query = query.where(AIGenerationBatch.status == status)
    if task_type:
        query = query.where(AIGenerationBatch.task_type == task_type)

    count_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(query.limit(limit).offset(offset))
    batches = result.scalars().all()

    return {
        "items": [
            {
                "batch_id": str(b.id),
                "task_type": b.task_type,
                "difficulty": b.difficulty,
                "status": b.status,
                "current_stage": b.current_stage,
                "created_at": b.created_at.isoformat() if b.created_at else None,
                "completed_at": b.completed_at.isoformat() if b.completed_at else None,
                "pass_rate": b.pass_rate,
                "selected_variant_id": str(b.selected_variant_id) if b.selected_variant_id else None,
                "attempt": b.attempt,
                "num_variants": b.num_variants,
            }
            for b in batches
        ],
        "total": total,
    }


@router.get("/ai-generate/analytics", response_model=list[AnalyticsResponse])
async def get_analytics(
    current_user_data: tuple = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> list[AnalyticsResponse]:
    """Только для админа: агрегированная статистика генерации по task_type и сложности."""
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
