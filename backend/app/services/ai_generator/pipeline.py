"""
GRPO-inspired generation pipeline for AI CTF challenges.

Flow per attempt:
  1. Generate N specs in parallel (asyncio.gather) with different temperatures
  2. Create artifacts in parallel
  3. Run binary reward checks per artifact
  4. Run LLM-as-judge quality assessment for variants that passed binary checks
  5. Compute group-relative advantages across ALL variants
  6. Rejection gate: keep only passed_all_binary == True
  7. Select variant with highest advantage among passed
  8. Store ALL variants in DB (winners and losers)
  9. If selected and reward >= threshold: done
  10. Otherwise accumulate failure_context and retry
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
from app.services.ai_generator.rag_context import RAGContextBuilder, RAGContext
from app.services.ai_generator.reward import (
    RewardCheck, VariantReward, compute_group_advantages, REWARD_WEIGHTS,
)
from app.services.ai_generator.reviewer import review_variant
from app.services.ai_generator.validator import validate
from app.services.prompt_loader import load_prompt_text, PromptLoadError

logger = logging.getLogger(__name__)

GENERATOR_MODEL_ID = "deepseek-v32"
GENERATOR_MODEL_VERSION = "latest"

_PROMPT_FILE_MAP: dict[str, str] = {
    "crypto_text_web": "crypto_generator.txt",
}

_generator_client: Optional[OpenAI] = None


class PipelineError(RuntimeError):
    pass


def _build_generator_client() -> OpenAI:
    global _generator_client
    api_key = (settings.YANDEX_CLOUD_API_KEY or "").strip()
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    missing: list[str] = []
    if not api_key:
        missing.append("YANDEX_CLOUD_API_KEY (or YANDEX_API_KEY / YC_API_KEY)")
    if not folder:
        missing.append("YANDEX_CLOUD_FOLDER (or YANDEX_CLOUD_FOLDER_ID / YANDEX_FOLDER_ID)")
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
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
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
) -> str:
    parts = [f'Generate a {difficulty} difficulty challenge.']
    if rag_context_text:
        parts.append("")
        parts.append(rag_context_text)
    if failure_context:
        parts.append("\nAvoid these common mistakes from previous attempts:")
        parts.extend(f"- {reason}" for reason in failure_context[-5:])
    return "\n".join(parts)


def _run_one_spec(
    *,
    task_type: str,
    difficulty: str,
    temperature: float,
    failure_context: list[str],
    rag_context_text: str = "",
) -> tuple[Optional[dict], Optional[str], int, int, int]:
    """Sync LLM call — runs in a thread via asyncio.to_thread."""
    client = _build_generator_client()
    folder = settings.YANDEX_CLOUD_FOLDER.strip()
    model = f"gpt://{folder}/{GENERATOR_MODEL_ID}/{GENERATOR_MODEL_VERSION}"
    reasoning_effort = settings.YANDEX_REASONING_EFFORT or "medium"
    system_prompt = _load_system_prompt(task_type)
    user_message = _build_user_message(difficulty, failure_context, rag_context_text)

    start = time.monotonic()
    try:
        response = client.chat.completions.create(
            model=model,
            reasoning_effort=reasoning_effort,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
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
) -> tuple[Optional[dict], Optional[str], int, int, int]:
    """Async wrapper — runs sync LLM call in a thread."""
    return await asyncio.to_thread(
        _run_one_spec,
        task_type=task_type,
        difficulty=difficulty,
        temperature=temperature,
        failure_context=failure_context,
        rag_context_text=rag_context_text,
    )


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
) -> None:
    """
    Main pipeline entry point. Runs inside a BackgroundTask.
    Updates ai_generation_batches and ai_generation_variants in DB.
    """
    folder = settings.YANDEX_CLOUD_FOLDER.strip()
    model_name = f"gpt://{folder}/{GENERATOR_MODEL_ID}/{GENERATOR_MODEL_VERSION}"

    max_retries = settings.AI_GEN_MAX_RETRIES
    base_temp = settings.AI_GEN_BASE_TEMPERATURE
    temp_step = settings.AI_GEN_TEMPERATURE_STEP
    threshold = settings.AI_GEN_MIN_REWARD_THRESHOLD

    # Build RAG context in its own session so any DB error (e.g. missing table)
    # cannot abort the pipeline session's transaction.
    from app.database import AsyncSessionLocal
    rag_context: RAGContext = RAGContext()
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

    failure_context: list[str] = []
    variant_counter = 0

    for attempt in range(1, max_retries + 1):
        logger.info("Pipeline batch=%s attempt=%d/%d", batch_id, attempt, max_retries)

        # Update batch attempt counter
        batch_result = await db.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == batch_id))
        batch = batch_result.scalar_one_or_none()
        if not batch:
            logger.error("Batch %s not found", batch_id)
            return
        batch.attempt = attempt
        batch.status = "generating"
        # Store RAG context metadata on first attempt
        if attempt == 1 and not rag_context.is_empty:
            batch.rag_context_ids = rag_context.entry_ids or None
            batch.rag_query_text = rag_context.query_text or None
            batch.rag_context_summary = rag_context_text[:500] if rag_context_text else None
        await db.commit()

        # ── Step 1: Generate N specs in parallel ─────────────────────────────
        temperatures = [base_temp + i * temp_step for i in range(num_variants)]
        generation_tasks = [
            _generate_one_spec(
                task_type=task_type,
                difficulty=difficulty,
                temperature=temp,
                failure_context=failure_context,
                rag_context_text=rag_context_text,
            )
            for temp in temperatures
        ]
        gen_results = await asyncio.gather(*generation_tasks, return_exceptions=True)

        # ── Step 2: Create artifacts in parallel ─────────────────────────────
        specs_and_meta: list[tuple[Optional[dict], Optional[str], float, int, int, int]] = []
        for i, result in enumerate(gen_results):
            if isinstance(result, Exception):
                specs_and_meta.append((None, str(result), temperatures[i], 0, 0, 0))
            else:
                spec, err, tok_in, tok_out, ms = result
                specs_and_meta.append((spec, err, temperatures[i], tok_in, tok_out, ms))

        artifact_tasks = [
            create_artifact(task_type, spec) if spec is not None else _failed_artifact(err)
            for spec, err, *_ in specs_and_meta
        ]
        artifacts: list[ArtifactResult] = await asyncio.gather(*artifact_tasks, return_exceptions=True)

        # ── Step 3 & 4: Validate and score each variant ───────────────────────
        variant_rewards: list[VariantReward] = []
        variant_data: list[dict] = []

        for i, ((spec, gen_err, temp, tok_in, tok_out, gen_ms), artifact) in enumerate(
            zip(specs_and_meta, artifacts)
        ):
            variant_counter += 1
            if isinstance(artifact, Exception):
                artifact = ArtifactResult(error=str(artifact))

            # Run binary checks
            if spec is not None and not artifact.error:
                checks = await validate(task_type, spec, artifact, rag_context)
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

            # Run LLM quality assessment only for passed variants (saves tokens)
            quality_score = None
            quality_details = None
            if vr.passed_all_binary and spec is not None:
                try:
                    quality_score, quality_details = await review_variant(spec, task_type, difficulty)
                    # Inject quality into checks for total_reward recalculation
                    from app.services.ai_generator.reward import RewardType, REWARD_WEIGHTS
                    q_weight = REWARD_WEIGHTS.get(task_type, {}).get(RewardType.QUALITY, 2.0)
                    checks.append(RewardCheck(
                        type=RewardType.QUALITY,
                        score=quality_score,
                        weight=q_weight,
                        detail=f"LLM quality assessment: {quality_score:.3f}",
                    ))
                    vr.compute()  # recalculate with quality included
                except Exception as exc:
                    logger.warning("Quality review failed for variant %d: %s", i, exc)

            variant_rewards.append(vr)
            variant_data.append({
                "spec": spec,
                "artifact": artifact,
                "gen_error": gen_err,
                "temperature": temp,
                "tokens_input": tok_in,
                "tokens_output": tok_out,
                "generation_time_ms": gen_ms,
                "quality_score": quality_score,
                "quality_details": quality_details,
            })

        # ── Step 5: Compute group-relative advantages ─────────────────────────
        compute_group_advantages(variant_rewards)

        # Assign ranks among passed variants
        passed = [(i, vr) for i, vr in enumerate(variant_rewards) if vr.passed_all_binary]
        passed_sorted = sorted(passed, key=lambda x: x[1].advantage, reverse=True)
        rank_map: dict[int, int] = {idx: rank + 1 for rank, (idx, _) in enumerate(passed_sorted)}

        # ── Step 8: Store ALL variants in DB ──────────────────────────────────
        stored_variants: list[AIGenerationVariant] = []
        for i, (vr, vdata) in enumerate(zip(variant_rewards, variant_data)):
            artifact = vdata["artifact"]
            artifact_dict = {
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
                id=uuid.uuid4(),
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

        # ── Step 9: Select best variant ───────────────────────────────────────
        if passed_sorted:
            best_idx, best_reward = passed_sorted[0]
            best_variant = stored_variants[best_idx]

            if best_reward.total_reward >= threshold:
                best_variant.is_selected = True
                best_variant.rank_in_group = 1

                # Update batch with results
                total_scores = [vr.total_reward for vr in variant_rewards]
                import statistics
                batch.group_mean_reward = statistics.mean(total_scores)
                batch.group_std_reward = statistics.stdev(total_scores) if len(total_scores) > 1 else 0.0
                batch.pass_rate = len(passed) / len(variant_rewards)
                batch.selected_variant_id = best_variant.id
                batch.status = "completed"
                from datetime import datetime, timezone
                batch.completed_at = datetime.now(timezone.utc)

                await db.commit()
                logger.info(
                    "Pipeline DONE batch=%s selected=%s reward=%.3f",
                    batch_id, best_variant.id, best_reward.total_reward,
                )
                return

        # ── Step 10: Accumulate failure context for next retry ────────────────
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

    # All attempts exhausted
    batch_result = await db.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == batch_id))
    batch = batch_result.scalar_one_or_none()
    if batch:
        batch.status = "failed"
        batch.failure_reasons_summary = {"failure_context": failure_context[-10:]}
        from datetime import datetime, timezone
        batch.completed_at = datetime.now(timezone.utc)
        await db.commit()
    logger.error("Pipeline FAILED batch=%s after %d attempts", batch_id, max_retries)


async def _failed_artifact(error: Optional[str]) -> ArtifactResult:
    from app.services.ai_generator.artifact_creator import ArtifactResult
    return ArtifactResult(error=error or "generation failed")
