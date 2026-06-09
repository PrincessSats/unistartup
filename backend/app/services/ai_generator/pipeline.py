"""
Конвейер генерации CTF-заданий, вдохновлённый GRPO.

Поток на каждую попытку:
  1. Генерировать N спеков параллельно (asyncio.gather) с разными температурами
  2. Создавать артефакты параллельно
  3. Запускать двоичные проверки вознаграждения для каждого артефакта
  4. Запускать оценку качества LLM-as-judge для вариантов, прошедших двоичные проверки
  5. Вычислять групп-относительные преимущества по ВСЕМ вариантам
  6. Ворота отбора: сохранять только passed_all_binary == True
  7. Выбирать вариант с наибольшим преимуществом среди прошедших
  8. Сохранять ВСЕ варианты в БД (победители и проигравшие)
  9. Если выбран и вознаграждение >= порога: готово
  10. Иначе накапливать failure_context и повторять
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any, Optional

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.ai_generation import AIGenerationBatch, AIGenerationVariant
from app.services.ai_generator.artifact_creator import create_artifact, ArtifactResult
from app.services.ai_generator.feedback import FeedbackContext, compute_feedback_context
from app.services.ai_generator.llm_retry import llm_call_with_retry
from app.services.ai_generator.rag_context import RAGContextBuilder, RAGContext
from app.services.ai_generator.reward import (
    RewardCheck, VariantReward, compute_group_advantages, REWARD_WEIGHTS,
)
from app.services.ai_generator.reviewer import review_variant
from app.services.ai_generator.validator import validate
from app.services.prompt_loader import load_prompt_text, PromptLoadError

logger = logging.getLogger(__name__)

GENERATOR_MODEL_ID = "deepseek-v4-flash"
GENERATOR_MODEL_VERSION = "latest"

_PROMPT_FILE_MAP: dict[str, str] = {
    "crypto_text_web": "crypto_generator.txt",
    "forensics_image_metadata": "forensics_generator.txt",
    "web_static_xss": "xss_generator.txt",
    "chat_llm": "chat_llm_generator.txt",
}

_generator_client: Optional[OpenAI] = None

# Общий лимит параллельности для ВСЕХ вызовов LLM в процессе (генерация + судья).
# Задаётся из settings.AI_GEN_MAX_CONCURRENT_LLM при первом использовании. 0/отсутствует = без ограничений.
# Позволяет нескольким параллельным процессам оставаться в рамках квоты сессий Yandex
# (лимит × n_процессов ≤ квота) без троттлинга.
_llm_semaphore: Optional[asyncio.Semaphore] = None
_llm_sem_init = False


def _get_llm_sem() -> Optional[asyncio.Semaphore]:
    global _llm_semaphore, _llm_sem_init
    if not _llm_sem_init:
        limit = int(getattr(settings, "AI_GEN_MAX_CONCURRENT_LLM", 0) or 0)
        _llm_semaphore = asyncio.Semaphore(limit) if limit > 0 else None
        _llm_sem_init = True
        if _llm_semaphore is not None:
            logger.info("LLM concurrency cap active: max %d in-flight calls/process", limit)
    return _llm_semaphore


async def _bounded(coro):
    """Ожидать `coro` под процессным семафором LLM (если настроен)."""
    sem = _get_llm_sem()
    if sem is None:
        return await coro
    async with sem:
        return await coro


class PipelineError(RuntimeError):
    pass


def _build_generator_client() -> OpenAI:
    global _generator_client
    api_key = (settings.YANDEX_CLOUD_API_KEY or "").strip()
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    missing: list[str] = []
    if not api_key:
        missing.append("YANDEX_CLOUD_API_KEY (или YANDEX_API_KEY / YC_API_KEY)")
    if not folder:
        missing.append("YANDEX_CLOUD_FOLDER (или YANDEX_CLOUD_FOLDER_ID / YANDEX_FOLDER_ID)")
    if missing:
        raise PipelineError(f"Missing Yandex LLM config: {', '.join(missing)}")
    if _generator_client is None:
        _generator_client = OpenAI(
            api_key=api_key,
            base_url="https://llm.api.cloud.yandex.net/v1",
            project=folder,
        )
    return _generator_client


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]  # убрать открывающий блок кода
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]  # убрать закрывающий блок кода
    return "\n".join(lines).strip()


def _load_system_prompt(task_type: str) -> str:
    filename = _PROMPT_FILE_MAP.get(task_type)
    if not filename:
        raise PipelineError(f"No prompt file configured for task_type={task_type!r}")
    try:
        return load_prompt_text(filename)
    except PromptLoadError as exc:
        raise PipelineError(str(exc)) from exc


def _build_user_message(
    difficulty: str,
    failure_context: list[str],
    rag_context_text: str = "",
    feedback_text: str = "",
) -> str:
    difficulty_ru = {
        "beginner": "начального",
        "intermediate": "среднего",
        "advanced": "продвинутого",
    }.get(difficulty, difficulty)
    parts = [f'Создай задание уровня сложности {difficulty_ru}.']
    if feedback_text:
        parts.append("")
        parts.append(feedback_text)
    if rag_context_text:
        parts.append("")
        parts.append(rag_context_text)
    if failure_context:
        parts.append("\nИзбегай этих ошибок из предыдущих попыток:")
        parts.extend(f"- {reason}" for reason in failure_context[-5:])
    return "\n".join(parts)


def _run_one_spec(
    *,
    task_type: str,
    difficulty: str,
    temperature: float,
    failure_context: list[str],
    rag_context_text: str = "",
    feedback_text: str = "",
) -> tuple[Optional[dict], Optional[str], int, int, int]:
    """Синхронный вызов LLM — выполняется в потоке через asyncio.to_thread."""
    client = _build_generator_client()
    folder = settings.YANDEX_CLOUD_FOLDER.strip()
    model = f"gpt://{folder}/{GENERATOR_MODEL_ID}/{GENERATOR_MODEL_VERSION}"
    reasoning_effort = settings.YANDEX_REASONING_EFFORT or "high"  # уровень рассуждения для LLM
    system_prompt = _load_system_prompt(task_type)
    user_message = _build_user_message(difficulty, failure_context, rag_context_text, feedback_text)

    start = time.monotonic()
    try:
        response = llm_call_with_retry(lambda: client.chat.completions.create(
            model=model,
            reasoning_effort=reasoning_effort,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        ))
    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        logger.warning("LLM generation error: %s", exc)
        return None, str(exc), 0, 0, elapsed_ms

    elapsed_ms = int((time.monotonic() - start) * 1000)
    usage = response.usage
    tokens_in = usage.prompt_tokens if usage else 0
    tokens_out = usage.completion_tokens if usage else 0

    raw = (response.choices[0].message.content or "").strip()
    raw = _strip_code_fence(raw)

    try:
        spec = json.loads(raw)
        if not isinstance(spec, dict):
            return None, f"LLM returned non-dict JSON: {type(spec)}", tokens_in, tokens_out, elapsed_ms
        return spec, None, tokens_in, tokens_out, elapsed_ms
    except json.JSONDecodeError as exc:
        return None, f"JSON parse error: {exc} — raw={raw[:200]!r}", tokens_in, tokens_out, elapsed_ms


async def _generate_one_spec(
    *,
    task_type: str,
    difficulty: str,
    temperature: float,
    failure_context: list[str],
    rag_context_text: str = "",
    feedback_text: str = "",
) -> tuple[Optional[dict], Optional[str], int, int, int]:
    """Асинхронная обёртка — запускает синхронный вызов LLM в потоке."""
    return await asyncio.to_thread(
        _run_one_spec,
        task_type=task_type,
        difficulty=difficulty,
        temperature=temperature,
        failure_context=failure_context,
        rag_context_text=rag_context_text,
        feedback_text=feedback_text,
    )


async def _update_stage(db: AsyncSession, batch_id: uuid.UUID, stage: str, meta: Optional[dict] = None) -> None:
    """Обновить текущий этап конвейера на строке пакета."""
    from datetime import datetime, timezone
    result = await db.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == batch_id))
    batch = result.scalar_one_or_none()
    if batch:
        batch.current_stage = stage
        batch.stage_started_at = datetime.now(timezone.utc)
        batch.stage_meta = meta
        await db.commit()


async def run_pipeline(
    *,
    task_type: str,
    difficulty: str,
    num_variants: int,
    user_id: Optional[int],
    batch_id: uuid.UUID,
    db: AsyncSession,
    cve_id: Optional[str] = None,
    topic: Optional[str] = None,
    inject_rag: bool = True,
    enable_self_test: bool = True,
) -> None:
    """
    Главная точка входа конвейера. Выполняется внутри BackgroundTask.
    Обновляет ai_generation_batches и ai_generation_variants в БД.
    """
    folder = settings.YANDEX_CLOUD_FOLDER.strip()
    model_name = f"gpt://{folder}/{GENERATOR_MODEL_ID}/{GENERATOR_MODEL_VERSION}"

    max_retries = settings.AI_GEN_MAX_RETRIES
    base_temp = settings.AI_GEN_BASE_TEMPERATURE
    temp_step = settings.AI_GEN_TEMPERATURE_STEP
    threshold = settings.AI_GEN_MIN_REWARD_THRESHOLD

    # Построить контекст RAG в отдельной сессии, чтобы любая ошибка БД (например, отсутствующая таблица)
    # не могла прервать транзакцию сессии конвейера.
    # inject_rag=False пропускает RAG полностью (используется в ablation-экспериментах); в продакшне всегда True.
    # ПРИМЕЧАНИЕ: AsyncSessionLocal импортируется здесь (не внутри блока `if inject_rag`), потому что
    # блок feedback-context ниже тоже его использует — безусловный импорт гарантирует,
    # что ablation без RAG случайно не отключит и цикл обратной связи.
    from app.database import AsyncSessionLocal
    rag_context: RAGContext = RAGContext()
    rag_context_text: str = ""
    if inject_rag:
        await _update_stage(db, batch_id, "rag_context")
        try:
            async with AsyncSessionLocal() as rag_session:
                rag_builder = RAGContextBuilder(rag_session)
                rag_context = await rag_builder.build_context(
                    task_type=task_type,
                    difficulty=difficulty,
                    specific_cve=cve_id,
                    specific_topic=topic,
                )
        except Exception as exc:
            logger.warning("RAG context builder failed, continuing without RAG: %s", exc)
        rag_context_text = rag_context.to_prompt_section()
        logger.info(
            "RAG context: %d entries, query=%r",
            len(rag_context.cve_entries), rag_context.query_text,
        )
        batch_result = await db.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == batch_id))
        batch = batch_result.scalar_one_or_none()
        if batch:
            batch.rag_context_ids = rag_context.entry_ids or None
            batch.rag_query_text = rag_context.query_text or None
            batch.rag_context_summary = rag_context_text[:500] if rag_context_text else None
            batch.stage_meta = {
                "rag_entries": len(rag_context.cve_entries),
                "rag_required": settings.AI_GEN_REQUIRE_RAG,
            }
            await db.commit()
            if settings.AI_GEN_REQUIRE_RAG and rag_context.is_empty:
                from datetime import datetime, timezone
                batch.status = "failed"
                batch.current_stage = "failed"
                batch.failure_reasons_summary = {
                    "failure_context": ["RAG context is required but no KB entries were loaded"],
                    "rag_query_text": rag_context.query_text,
                }
                batch.completed_at = datetime.now(timezone.utc)
                await db.commit()
                logger.error("Pipeline FAILED batch=%s: required RAG context is empty", batch_id)
                return
    else:
        logger.info("RAG injection disabled (inject_rag=False; ablation experiment no_rag condition)")

    # Построить контекст обратной связи из исторических генераций (few-shot примеры)
    feedback_ctx = FeedbackContext()
    try:
        async with AsyncSessionLocal() as fb_session:
            feedback_ctx = await compute_feedback_context(task_type, difficulty, fb_session)
        logger.info(
            "Feedback context: %d positive examples, %d negative patterns, pass_rate=%s",
            len(feedback_ctx.positive_examples),
            len(feedback_ctx.negative_patterns),
            f"{feedback_ctx.recent_pass_rate:.1%}" if feedback_ctx.recent_pass_rate is not None else "n/a",
        )
    except Exception as exc:
        logger.warning("Feedback context failed, continuing without: %s", exc)
    feedback_text = feedback_ctx.format_for_prompt()

    failure_context: list[str] = []
    variant_counter = 0

    for attempt in range(1, max_retries + 1):
        logger.info("Pipeline batch=%s attempt=%d/%d", batch_id, attempt, max_retries)

        # Обновить счетчик попыток пакета
        batch_result = await db.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == batch_id))
        batch = batch_result.scalar_one_or_none()
        if not batch:
            logger.error("Batch %s not found", batch_id)
            return
        batch.attempt = attempt
        batch.status = "generating"
        await db.commit()

        # ── Шаг 1: Генерировать N спецификаций параллельно ─────────────────────────────
        await _update_stage(db, batch_id, "spec_generation", {"num_variants": num_variants})
        temperatures = [base_temp + i * temp_step for i in range(num_variants)]
        generation_tasks = [
            _bounded(_generate_one_spec(
                task_type=task_type,
                difficulty=difficulty,
                temperature=temp,
                failure_context=failure_context,
                rag_context_text=rag_context_text,
                feedback_text=feedback_text,
            ))
            for temp in temperatures
        ]
        gen_results = await asyncio.gather(*generation_tasks, return_exceptions=True)

        # ── Шаг 2: Создать артефакты параллельно ─────────────────────────────
        specs_and_meta: list[tuple[Optional[dict], Optional[str], float, int, int, int]] = []
        for i, result in enumerate(gen_results):
            if isinstance(result, Exception):
                specs_and_meta.append((None, str(result), temperatures[i], 0, 0, 0))
            else:
                spec, err, tok_in, tok_out, ms = result
                specs_and_meta.append((spec, err, temperatures[i], tok_in, tok_out, ms))

        await _update_stage(db, batch_id, "artifact_creation")
        variant_uuids = [uuid.uuid4() for _ in specs_and_meta]
        artifact_tasks = [
            create_artifact(task_type, spec, batch_id=str(batch_id), variant_id=str(variant_uuids[i]))
            if spec is not None else _failed_artifact(err)
            for i, (spec, err, *_) in enumerate(specs_and_meta)
        ]
        artifacts: list[ArtifactResult] = await asyncio.gather(*artifact_tasks, return_exceptions=True)

        # ── Шаги 3 & 4: Проверить и оценить каждый вариант ───────────────────────
        await _update_stage(db, batch_id, "validation")
        variant_rewards: list[VariantReward] = []
        variant_data: list[dict] = []

        # ── Фаза A: двоичная валидация каждого варианта (последовательно — контейнер
        #    XSS self-test имеет параллельность=1, так что gather не поможет;
        #    не-XSS проверки быстрые, внутрипроцессные). ────────────────────────────
        for i, ((spec, gen_err, temp, tok_in, tok_out, gen_ms), artifact) in enumerate(
            zip(specs_and_meta, artifacts)
        ):
            variant_counter += 1
            if isinstance(artifact, Exception):
                artifact = ArtifactResult(error=str(artifact))

            # Запустить двоичные проверки вознаграждения
            if spec is not None and not artifact.error:
                checks = await validate(task_type, spec, artifact, rag_context, enable_self_test=enable_self_test)
            else:
                from app.services.ai_generator.reward import RewardType
                checks = [RewardCheck(
                    type=RewardType.FUNCTIONAL,
                    score=0.0,
                    weight=1.0,
                    detail="Generation or artifact creation failed",
                    error=gen_err or artifact.error,
                )]

            vr = VariantReward(variant_number=variant_counter, checks=checks)
            vr.compute()

            variant_rewards.append(vr)
            variant_data.append({
                "spec": spec,
                "artifact": artifact,
                "gen_error": gen_err,
                "temperature": temp,
                "tokens_input": tok_in,
                "tokens_output": tok_out,
                "generation_time_ms": gen_ms,
                "quality_score": None,
                "quality_details": None,
            })

        # ── Фаза B: оценка качества LLM-as-judge для вариантов, прошедших все
        #    двоичные ворота — выполняется ПАРАЛЛЕЛЬНО (раньше было последовательно).
        #    Одинаковая модель/промпты/оценка → идентичное качество; только wall-clock
        #    этого этапа снижается с sum() до max(). Пиковая параллельность = #passed ≤ N,
        #    запускается после завершения генерации, поэтому остаётся в рамках квоты LLM. ─
        review_idx = [
            i for i, (vr, vd) in enumerate(zip(variant_rewards, variant_data))
            if vr.passed_all_binary and vd["spec"] is not None
        ]
        if review_idx:
            await _update_stage(db, batch_id, "llm_quality_review", {"count": len(review_idx)})
            review_results = await asyncio.gather(
                *[
                    _bounded(review_variant(variant_data[i]["spec"], task_type, difficulty))
                    for i in review_idx
                ],
                return_exceptions=True,
            )
            from app.services.ai_generator.reward import RewardType, REWARD_WEIGHTS
            q_weight = REWARD_WEIGHTS.get(task_type, {}).get(RewardType.QUALITY, 2.0)
            for i, res in zip(review_idx, review_results):
                if isinstance(res, Exception):
                    logger.warning("Quality review failed for variant %d: %s", i, res)
                    continue
                quality_score, quality_details = res
                vr = variant_rewards[i]
                vr.checks.append(RewardCheck(
                    type=RewardType.QUALITY,
                    score=quality_score,
                    weight=q_weight,
                    detail=f"LLM quality assessment: {quality_score:.3f}",
                ))
                vr.compute()  # пересчитать с учётом качества
                variant_data[i]["quality_score"] = quality_score
                variant_data[i]["quality_details"] = quality_details

        # ── Шаг 5: Вычислить относительные преимущества группы ─────────────────────────
        await _update_stage(db, batch_id, "grpo_computation")
        compute_group_advantages(variant_rewards)

        # Назначить рейтинги среди прошедших вариантов
        passed = [(i, vr) for i, vr in enumerate(variant_rewards) if vr.passed_all_binary]
        passed_sorted = sorted(passed, key=lambda x: x[1].advantage, reverse=True)
        rank_map: dict[int, int] = {idx: rank + 1 for rank, (idx, _) in enumerate(passed_sorted)}

        # ── Шаг 8: Сохранить ВСЕ варианты в БД ──────────────────────────────────
        stored_variants: list[AIGenerationVariant] = []
        for i, (vr, vdata) in enumerate(zip(variant_rewards, variant_data)):
            artifact = vdata["artifact"]
            artifact_dict = {  # type: ignore[assignment]
                "content": artifact.content,
                "file_url": artifact.file_url,
                "verification_data": artifact.verification_data,
                "error": artifact.error,
            } if artifact else None

            checks_list = [
                {
                    "type": c.type.value,
                    "score": c.score,
                    "weight": c.weight,
                    "detail": c.detail,
                    "error": c.error,
                }
                for c in vr.checks
            ]

            failure = vdata["gen_error"]
            if not failure and not vr.passed_all_binary:
                failed_checks = [c for c in vr.checks if c.score < 1.0 and c.is_binary()]
                failure = "; ".join(f"{c.type.value}: {c.detail}" for c in failed_checks)

            variant = AIGenerationVariant(
                id=variant_uuids[i],
                batch_id=batch_id,
                variant_number=vr.variant_number,
                model_used=model_name,
                temperature=vdata["temperature"],
                tokens_input=vdata["tokens_input"],
                tokens_output=vdata["tokens_output"],
                generation_time_ms=vdata["generation_time_ms"],
                generated_spec=vdata["spec"],
                artifact_result=artifact_dict,
                reward_checks=checks_list,
                reward_total=vr.total_reward,
                reward_binary=vr.binary_reward,
                passed_all_binary=vr.passed_all_binary,
                quality_score=vdata["quality_score"],
                quality_details=vdata["quality_details"],
                advantage=vr.advantage,
                rank_in_group=rank_map.get(i),
                is_selected=False,
                failure_reason=failure,
            )
            db.add(variant)
            stored_variants.append(variant)

        await db.commit()

        # Встроить спецификации вариантов для будущего поиска похожести обратной связи (неблокирующее)
        asyncio.create_task(_embed_variants_background(stored_variants))

        # ── Шаг 9: Выбрать лучший вариант ───────────────────────────────────────
        await _update_stage(db, batch_id, "selection", {"pass_rate": len(passed) / max(len(variant_rewards), 1)})
        if passed_sorted:
            best_idx, best_reward = passed_sorted[0]
            best_variant = stored_variants[best_idx]

            if best_reward.total_reward >= threshold:
                best_variant.is_selected = True
                best_variant.rank_in_group = 1

                # Обновить пакет с результатами
                total_scores = [vr.total_reward for vr in variant_rewards]
                import statistics
                batch.group_mean_reward = statistics.mean(total_scores)
                batch.group_std_reward = statistics.stdev(total_scores) if len(total_scores) > 1 else 0.0
                batch.pass_rate = len(passed) / len(variant_rewards)
                batch.selected_variant_id = best_variant.id
                batch.status = "completed"
                batch.current_stage = "completed"
                from datetime import datetime, timezone
                batch.completed_at = datetime.now(timezone.utc)

                await db.commit()
                logger.info(
                    "Pipeline DONE batch=%s selected=%s reward=%.3f",
                    batch_id, best_variant.id, best_reward.total_reward,
                )
                return

        # ── Шаг 10: Накопить контекст ошибок для следующей попытки ────────────────
        new_failures = []
        for vr in variant_rewards:
            if not vr.passed_all_binary:
                failed = [c for c in vr.checks if c.score < 1.0 and c.is_binary()]
                new_failures.extend(f"{c.type.value}: {c.detail}" for c in failed)
        failure_context.extend(new_failures[:5])
        logger.warning(
            "Pipeline attempt=%d failed — pass_rate=%.0f%% new_failures=%d",
            attempt, (len(passed) / max(len(variant_rewards), 1)) * 100, len(new_failures),
        )

    # Все попытки исчерпаны
    batch_result = await db.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == batch_id))
    batch = batch_result.scalar_one_or_none()
    if batch:
        batch.status = "failed"
        batch.current_stage = "failed"
        batch.failure_reasons_summary = {"failure_context": failure_context[-10:]}
        from datetime import datetime, timezone
        batch.completed_at = datetime.now(timezone.utc)
        await db.commit()
    logger.error("Pipeline FAILED batch=%s after %d attempts", batch_id, max_retries)


async def _failed_artifact(error: Optional[str]) -> ArtifactResult:
    from app.services.ai_generator.artifact_creator import ArtifactResult
    return ArtifactResult(error=error or "generation failed")


async def _embed_variants_background(variants: list[AIGenerationVariant]) -> None:
    """
    Встроить спецификации вариантов и сохранить в БД для будущего поиска похожести обратной связи.
    Выполняется как фоновая задача — ошибки регистрируются, но никогда не выбрасываются.
    Открывает свою собственную сессию БД, чтобы избежать помех основной сессии конвейера.
    """
    from app.database import AsyncSessionLocal
    from app.services.ai_generator.embedding_service import EmbeddingService, EmbeddingError

    svc = EmbeddingService()
    try:
        async with AsyncSessionLocal() as db:
            for variant in variants:
                spec = variant.generated_spec
                if not spec:
                    continue
                text = " ".join(filter(None, [
                    spec.get("title", ""),
                    spec.get("description", ""),
                ]))
                if not text.strip():
                    continue
                try:
                    embedding = await svc.embed_document(text)
                    # Перезагрузить вариант в этой сессии, чтобы избежать перекрёстного состояния
                    result = await db.execute(
                        select(AIGenerationVariant).where(AIGenerationVariant.id == variant.id)
                    )
                    v = result.scalar_one_or_none()
                    if v:
                        v.embedding = embedding
                except EmbeddingError as exc:
                    logger.debug("Embedding skipped for variant %s: %s", variant.id, exc)
            await db.commit()
    except Exception as exc:
        logger.warning("_embed_variants_background failed: %s", exc)
    finally:
        await svc.close()
