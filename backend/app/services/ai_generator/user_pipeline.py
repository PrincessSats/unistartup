"""
Конвейер генерации варианта задачи пользователя.

Упрощённая версия административного конвейера для сгенерированных пользователем вариантов задач.
Включает полный обзор качества LLM (не пропускается).

Поток:
  1. Загрузить родительскую задачу (только crypto/forensics/web, НЕ chat)
  2. Построить контекст RAG из категории/CVE родительской задачи
  3. Генерировать 3 спека параллельно с разными температурами
  4. Создавать артефакты параллельно
  5. Запустить двоичные проверки вознаграждения для каждого артефакта
  6. Запустить оценку качества LLM-as-judge для прошедших вариантов
  7. Вычислить группоабсолютные преимущества (GRPO)
  8. Выбрать вариант с наибольшим преимуществом среди прошедших
  9. Сохранить ВСЕ варианты в БД
  10. Обновить статус запроса пользователя
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

from app.services.ai_generator.llm_retry import llm_call_with_retry

from app.config import settings
from app.models.ai_generation import AIGenerationBatch, AIGenerationVariant
from app.models.user_task_variant import UserTaskVariantRequest
from app.services.ai_generator.artifact_creator import create_artifact, ArtifactResult
from app.services.ai_generator.rag_context import RAGContextBuilder, RAGContext
from app.services.ai_generator.reward import (
    RewardCheck, VariantReward, compute_group_advantages, REWARD_WEIGHTS,
)
from app.services.ai_generator.reviewer import review_variant
from app.services.ai_generator.validator import validate
from app.services.prompt_loader import load_prompt_text, PromptLoadError
from app.services.ai_generator.prompt_safety import SafetyCheckResult

logger = logging.getLogger(__name__)

GENERATOR_MODEL_ID = "deepseek-v4-flash"
GENERATOR_MODEL_VERSION = "latest"

# Prompt file mapping for user variants (excludes chat_llm)
_PROMPT_FILE_MAP: dict[str, str] = {
    "crypto_text_web": "crypto_generator.txt",
    "forensics_image_metadata": "forensics_generator.txt",
    "web_static_xss": "xss_generator.txt",
}

_generator_client: Optional[OpenAI] = None


class UserPipelineError(RuntimeError):
    pass


def _build_generator_client() -> OpenAI:
    """Создать или повторно использовать клиент OpenAI для Yandex Cloud LLM."""
    global _generator_client
    api_key = (settings.YANDEX_CLOUD_API_KEY or "").strip()
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    missing: list[str] = []
    if not api_key:
        missing.append("YANDEX_CLOUD_API_KEY")
    if not folder:
        missing.append("YANDEX_CLOUD_FOLDER")
    if missing:
        raise UserPipelineError(f"Missing Yandex LLM config: {', '.join(missing)}")
    if _generator_client is None:
        _generator_client = OpenAI(
            api_key=api_key,
            base_url="https://llm.api.cloud.yandex.net/v1",
            project=folder,
        )
    return _generator_client


def _strip_code_fence(text: str) -> str:
    """Удалить markdown ограды кода из ответа LLM."""
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _load_system_prompt(task_type: str) -> str:
    """Загрузить системный промпт из файла."""
    filename = _PROMPT_FILE_MAP.get(task_type)
    if not filename:
        raise UserPipelineError(f"No prompt file configured for task_type={task_type!r}")
    try:
        return load_prompt_text(filename)
    except PromptLoadError as exc:
        raise UserPipelineError(str(exc)) from exc


def _build_user_message(
    parent_task_title: str,
    parent_task_description: str,
    user_wishes: str,
    rag_context_text: str = "",
) -> str:
    """Построить сообщение пользователя для LLM с контекстом родительской задачи и пожеланиями пользователя."""
    parts = [
        f"\u0421\u043e\u0437\u0434\u0430\u0439 \u0432\u0430\u0440\u0438\u0430\u043d\u0442 \u0437\u0430\u0434\u0430\u043d\u0438\u044f \u043d\u0430 \u043e\u0441\u043d\u043e\u0432\u0435 \u0441\u0443\u0449\u0435\u0441\u0442\u0432\u0443\u044e\u0449\u0435\u0433\u043e \u0437\u0430\u0434\u0430\u043d\u0438\u044f.",
        "",
        "## \u0418\u0441\u0445\u043e\u0434\u043d\u043e\u0435 \u0437\u0430\u0434\u0430\u043d\u0438\u0435 (\u0440\u043e\u0434\u0438\u0442\u0435\u043b\u044c)",
        f"**\u041d\u0430\u0437\u0432\u0430\u043d\u0438\u0435:** {parent_task_title}",
        f"**\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435:** {parent_task_description[:300]}..." if len(parent_task_description) > 300 else f"**\u041e\u043f\u0438\u0441\u0430\u043d\u0438\u0435:** {parent_task_description}",
        "",
        "## \u041f\u043e\u0436\u0435\u043b\u0430\u043d\u0438\u044f \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f (\u0443\u0447\u0442\u0438 \u0432 \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0438 \u0438 \u043c\u0435\u0445\u0430\u043d\u0438\u043a\u0435)",
        user_wishes,
        "",
        "**\u0412\u0410\u0416\u041d\u041e:** \u0421\u043e\u0437\u0434\u0430\u0439 \u0423\u041d\u0418\u041a\u0410\u041b\u042c\u041d\u042b\u0419 \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0439, \u043d\u0435 \u043a\u043e\u043f\u0438\u0440\u0443\u0439 \u043d\u0430\u0437\u0432\u0430\u043d\u0438\u0435 \u0438\u043b\u0438 \u043e\u043f\u0438\u0441\u0430\u043d\u0438\u0435 \u0440\u043e\u0434\u0438\u0442\u0435\u043b\u044f.",
        "\u0418\u0441\u043f\u043e\u043b\u044c\u0437\u0443\u0439 \u043c\u0435\u0445\u0430\u043d\u0438\u043a\u0443 (\u0442\u0438\u043f \u0448\u0438\u0444\u0440\u0430, \u0443\u044f\u0437\u0432\u0438\u043c\u043e\u0441\u0442\u044c) \u043a\u0430\u043a \u043e\u0441\u043d\u043e\u0432\u0443, \u043d\u043e \u0438\u0437\u043c\u0435\u043d\u0438 \u0441\u0446\u0435\u043d\u0430\u0440\u0438\u0439.",
    ]
    
    if rag_context_text:
        parts.append("")
        parts.append(rag_context_text)
    
    return "\n".join(parts)


def _run_one_spec(
    *,
    task_type: str,
    temperature: float,
    parent_task_title: str,
    parent_task_description: str,
    user_wishes: str,
    rag_context_text: str = "",
) -> tuple[Optional[dict], Optional[str], int, int, int]:
    """Синхронный вызов LLM — работает в потоке через asyncio.to_thread."""
    client = _build_generator_client()
    folder = settings.YANDEX_CLOUD_FOLDER.strip()
    model = f"gpt://{folder}/{GENERATOR_MODEL_ID}/{GENERATOR_MODEL_VERSION}"
    reasoning_effort = settings.YANDEX_REASONING_EFFORT or "high"
    system_prompt = _load_system_prompt(task_type)
    user_message = _build_user_message(
        parent_task_title,
        parent_task_description,
        user_wishes,
        rag_context_text,
    )

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
    temperature: float,
    parent_task_title: str,
    parent_task_description: str,
    user_wishes: str,
    rag_context_text: str = "",
) -> tuple[Optional[dict], Optional[str], int, int, int]:
    """Асинхронный обёртка — запускает синхронный вызов LLM в потоке."""
    return await asyncio.to_thread(
        _run_one_spec,
        task_type=task_type,
        temperature=temperature,
        parent_task_title=parent_task_title,
        parent_task_description=parent_task_description,
        user_wishes=user_wishes,
        rag_context_text=rag_context_text,
    )


async def _update_request_status(
    db: AsyncSession,
    request_id: uuid.UUID,
    status: str,
    variant_id: Optional[uuid.UUID] = None,
    failure_reason: Optional[str] = None,
) -> None:
    """Обновить статус запроса пользователя."""
    result = await db.execute(
        select(UserTaskVariantRequest).where(UserTaskVariantRequest.id == request_id)
    )
    request = result.scalar_one_or_none()
    if request:
        request.status = status
        if variant_id:
            request.generated_variant_id = variant_id
        if failure_reason:
            request.failure_reason = failure_reason
        if status in ("completed", "failed"):
            from datetime import datetime, timezone
            request.completed_at = datetime.now(timezone.utc)
        await db.commit()


async def run_user_variant_pipeline(
    *,
    parent_task_id: int,
    user_request: str,
    sanitized_request: str,
    user_id: int,
    request_id: uuid.UUID,
    db: AsyncSession = None,  # Сохранено для совместимости, но используется локальная сессия
) -> None:
    """
    Главная точка входа конвейера для вариантов пользователя.
    Работает внутри BackgroundTask.
    """
    from app.database import AsyncSessionLocal
    from app.models.contest import Task
    from app.models.ai_generation import AIGenerationBatch

    # Допустимые типы задач для вариантов пользователя (НЕ chat)
    ALLOWED_PARENT_CATEGORIES = {"Crypto", "Forensics", "Web"}
    CATEGORY_TO_TASK_TYPE = {
        "Crypto": "crypto_text_web",
        "Forensics": "forensics_image_metadata",
        "Web": "web_static_xss",
    }

    NUM_VARIANTS = 3  # Быстрее, чем 5 в админе
    BASE_TEMP = 0.8
    TEMP_STEP = 0.1
    THRESHOLD = settings.AI_GEN_MIN_REWARD_THRESHOLD or 0.6

    folder = settings.YANDEX_CLOUD_FOLDER.strip()
    model_name = f"gpt://{folder}/{GENERATOR_MODEL_ID}/{GENERATOR_MODEL_VERSION}"

    # Используется НОВАЯ сессия, потому что фоновые задачи выполняются после закрытия сессии запроса
    async with AsyncSessionLocal() as db:
        try:
            # Загрузить родительскую задачу
            parent_result = await db.execute(
                select(Task).where(Task.id == parent_task_id)
            )
            parent_task = parent_result.scalar_one_or_none()

            if not parent_task:
                await _update_request_status(
                    db, request_id, "failed",
                    failure_reason=f"Родительская задача {parent_task_id} не найдена",
                )
                return

            # Проверить категорию
            if parent_task.category not in ALLOWED_PARENT_CATEGORIES:
                await _update_request_status(
                    db, request_id, "failed",
                    failure_reason=f"Категория задачи '{parent_task.category}' не поддерживается для вариантов пользователя (допустимые: {', '.join(ALLOWED_PARENT_CATEGORIES)})",
                )
                return

            # Определить тип задачи из категории родителя
            task_type = CATEGORY_TO_TASK_TYPE.get(parent_task.category)
            if not task_type:
                await _update_request_status(
                    db, request_id, "failed",
                    failure_reason=f"Невозможно сопоставить категорию '{parent_task.category}' с типом задачи",
                )
                return

            # Создать запись пакета для отслеживания вариантов (требуется FK-ограничением)
            batch_id = uuid.uuid4()
            batch = AIGenerationBatch(
                id=batch_id,
                requested_by=user_id,
                task_type=task_type,
                difficulty="intermediate",
                num_variants=NUM_VARIANTS,
                status="generating",
                current_stage="starting",
            )
            db.add(batch)
            await db.commit()

            # Обновить статус запроса на "генерирование"
            await _update_request_status(db, request_id, "generating")

            # Построить контекст RAG
            rag_context: RAGContext = RAGContext()
            try:
                # Использовать локальную сессию 'db'
                rag_builder = RAGContextBuilder(db)
                # Использовать KB-запись родительской задачи, если существует
                specific_cve = None
                if parent_task.kb_entry_id:
                    from app.models.contest import KBEntry
                    kb_result = await db.execute(
                        select(KBEntry).where(KBEntry.id == parent_task.kb_entry_id)
                    )
                    kb_entry = kb_result.scalar_one_or_none()
                    if kb_entry and hasattr(kb_entry, "cve_id"):
                        specific_cve = kb_entry.cve_id

                rag_context = await rag_builder.build_context(
                    task_type=task_type,
                    difficulty="intermediate",  # По умолчанию для вариантов пользователя
                    specific_cve=specific_cve,
                    specific_topic=parent_task.title,
                )
            except Exception as exc:
                logger.warning("Построитель контекста RAG не пройден, продолжение без RAG: %s", exc)

            rag_context_text = rag_context.to_prompt_section()
            logger.info(
                "Контекст RAG варианта пользователя: %d записей, родительская_задача=%d",
                len(rag_context.cve_entries), parent_task_id,
            )

            # Генерировать N спеков параллельно
            temperatures = [BASE_TEMP + i * TEMP_STEP for i in range(NUM_VARIANTS)]
            generation_tasks = [
                _generate_one_spec(
                    task_type=task_type,
                    temperature=temp,
                    parent_task_title=parent_task.title,
                    parent_task_description=parent_task.participant_description or parent_task.story or "",
                    user_wishes=sanitized_request,
                    rag_context_text=rag_context_text,
                )
                for temp in temperatures
            ]
            gen_results = await asyncio.gather(*generation_tasks, return_exceptions=True)

            # Обработать результаты генерации
            specs_and_meta: list[tuple[Optional[dict], Optional[str], float, int, int, int]] = []
            for i, result in enumerate(gen_results):
                if isinstance(result, Exception):
                    specs_and_meta.append((None, str(result), temperatures[i], 0, 0, 0))
                else:
                    spec, err, tok_in, tok_out, ms = result
                    specs_and_meta.append((spec, err, temperatures[i], tok_in, tok_out, ms))

            # Создавать артефакты параллельно
            variant_uuids = [uuid.uuid4() for _ in specs_and_meta]
            artifact_tasks = [
                create_artifact(task_type, spec, batch_id=str(request_id), variant_id=str(variant_uuids[i]))
                if spec is not None else _failed_artifact(err)
                for i, (spec, err, *_) in enumerate(specs_and_meta)
            ]
            artifacts: list[ArtifactResult] = await asyncio.gather(*artifact_tasks, return_exceptions=True)

            # Валидировать и оценивать каждый вариант
            variant_rewards: list[VariantReward] = []
            variant_data: list[dict] = []
            
            for i, ((spec, gen_err, temp, tok_in, tok_out, gen_ms), artifact) in enumerate(
                zip(specs_and_meta, artifacts)
            ):
                if isinstance(artifact, Exception):
                    artifact = ArtifactResult(error=str(artifact))
                
                # Run binary checks (enable_self_test=True: XSS SOLVABILITY uses live
                # Playwright/Chromium verdict from Yandex Serverless Container when
                # AI_GEN_ENABLE_SELFTEST=true; falls back to static heuristic otherwise)
                if spec is not None and not artifact.error:
                    checks = await validate(task_type, spec, artifact, rag_context, enable_self_test=True)
                else:
                    from app.services.ai_generator.reward import RewardType
                    checks = [RewardCheck(
                        type=RewardType.FUNCTIONAL,
                        score=0.0,
                        weight=1.0,
                        detail="Generation or artifact creation failed",
                        error=gen_err or artifact.error,
                    )]
                
                vr = VariantReward(variant_number=i + 1, checks=checks)
                vr.compute()

                # Запустить оценку качества LLM для прошедших вариантов
                quality_score = None
                quality_details = None
                if vr.passed_all_binary and spec is not None:
                    try:
                        quality_score, quality_details = await review_variant(spec, task_type, "intermediate")
                        # Внедрить качество в проверки для пересчёта total_reward
                        from app.services.ai_generator.reward import RewardType, REWARD_WEIGHTS
                        q_weight = REWARD_WEIGHTS.get(task_type, {}).get(RewardType.QUALITY, 2.0)
                        checks.append(RewardCheck(
                            type=RewardType.QUALITY,
                            score=quality_score,
                            weight=q_weight,
                            detail=f"Оценка качества LLM: {quality_score:.3f}",
                        ))
                        vr.compute()  # Пересчитать с учётом качества
                    except Exception as exc:
                        logger.warning("Обзор качества не прошёлся для варианта %d: %s", i, exc)

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

            # Вычислить группоабсолютные преимущества (GRPO)
            compute_group_advantages(variant_rewards)

            # Назначить ранги среди прошедших вариантов
            passed = [(i, vr) for i, vr in enumerate(variant_rewards) if vr.passed_all_binary]
            passed_sorted = sorted(passed, key=lambda x: x[1].advantage, reverse=True)
            rank_map: dict[int, int] = {idx: rank + 1 for rank, (idx, _) in enumerate(passed_sorted)}

            # Сохранить ВСЕ варианты в БД
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
                    id=variant_uuids[i],
                    batch_id=batch_id,  # Use the batch we created
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
            
            # Выбрать лучший вариант
            if passed_sorted:
                best_idx, best_reward = passed_sorted[0]
                best_variant = stored_variants[best_idx]

                if best_reward.total_reward >= THRESHOLD:
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

                    # АВТОПУБЛИКАЦИЯ: Создать реальную задачу из варианта
                    from app.models.contest import Task, TaskFlag, TaskMaterial
                    spec = best_variant.generated_spec

                    if spec:
                        # Определить тип задачи на основе родителя
                        task_kind = "ugc"  # UGC-задачи теперь специально отмечены
                        task_state = "published"  # Автопубликация немедленно
                        
                        # \u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0437\u0430\u0434\u0430\u0447\u0443
                        new_task = Task(
                            title=spec.get("title", "UGC \u0412\u0430\u0440\u0438\u0430\u043d\u0442"),
                            category=parent_task.category,
                            difficulty=2,  # \u043f\u0440\u043e\u043c\u0435\u0436\u0443\u0442\u043e\u0447\u043d\u044b\u0439
                            points=100,
                            tags=["ugc", "community"] + (parent_task.tags or [])[:3],
                            task_kind=task_kind,
                            access_type=parent_task.access_type,
                            language="ru",
                            story=spec.get("description", ""),
                            participant_description=spec.get("description", ""),
                            state=task_state,
                            parent_id=parent_task_id,  # \u0421\u0441\u044b\u043b\u043a\u0430 \u043d\u0430 \u0440\u043e\u0434\u0438\u0442\u0435\u043b\u044c\u0441\u043a\u0443\u044e \u0437\u0430\u0434\u0430\u0447\u0443
                            created_by=user_id,
                        )
                        db.add(new_task)
                        await db.flush()  # \u041f\u043e\u043b\u0443\u0447\u0438\u0442\u044c ID \u0437\u0430\u0434\u0430\u0447\u0438

                        # \u0421\u043e\u0437\u0434\u0430\u0442\u044c \u0444\u043b\u0430\u0433
                        flag_value = spec.get("flag", "CTF{ugc_variant}")
                        task_flag = TaskFlag(
                            task_id=new_task.id,
                            flag_id="ugc_flag",
                            format="CTF{...}",
                            expected_value=flag_value,
                            description="\u0424\u043b\u0430\u0433 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u0430 UGC",
                        )
                        db.add(task_flag)

                        # \u0421\u043e\u0437\u0434\u0430\u0442\u044c \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b\u044b \u043d\u0430 \u043e\u0441\u043d\u043e\u0432\u0435 \u0442\u0438\u043f\u0430 \u0437\u0430\u0434\u0430\u0447\u0438
                        artifact = best_variant.artifact_result or {}

                        if task_type == "crypto_text_web" and artifact.get("content"):
                            # \u0414\u043e\u0431\u0430\u0432\u0438\u0442\u044c \u0437\u0430\u0448\u0438\u0444\u0440\u043e\u0432\u0430\u043d\u043d\u044b\u0439 \u0442\u0435\u043a\u0441\u0442 \u043a\u0430\u043a \u043c\u0430\u0442\u0435\u0440\u0438\u0430\u043b
                            material = TaskMaterial(
                                task_id=new_task.id,
                                type="text",
                                name="\u0417\u0430\u0448\u0438\u0444\u0440\u043e\u0432\u0430\u043d\u043d\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435",
                                description="\u041f\u0435\u0440\u0435\u0445\u0432\u0430\u0447\u0435\u043d\u043d\u043e\u0435 \u0437\u0430\u0448\u0438\u0444\u0440\u043e\u0432\u0430\u043d\u043d\u043e\u0435 \u0441\u043e\u043e\u0431\u0449\u0435\u043d\u0438\u0435",
                                meta={"content": artifact["content"]},
                            )
                            db.add(material)

                        elif task_type == "forensics_image_metadata" and artifact.get("file_url"):
                            # \u0421\u0441\u044b\u043b\u043a\u0430 \u043d\u0430 \u0441\u043e\u0437\u0434\u0430\u043d\u043d\u043e\u0435 \u0438\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435
                            material = TaskMaterial(
                                task_id=new_task.id,
                                type="file",
                                name="\u0418\u0437\u043e\u0431\u0440\u0430\u0436\u0435\u043d\u0438\u0435 \u0434\u043b\u044f \u0430\u043d\u0430\u043b\u0438\u0437\u0430",
                                description="\u0424\u043e\u0442\u043e\u0433\u0440\u0430\u0444\u0438\u044f \u0441 \u043c\u0435\u0442\u0430\u0434\u0430\u043d\u043d\u044b\u043c\u0438",
                                meta={"download_url": artifact["file_url"]},
                            )
                            db.add(material)

                        elif task_type == "web_static_xss" and artifact.get("file_url"):
                            # \u0421\u0441\u044b\u043b\u043a\u0430 \u043d\u0430 \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0443 XSS
                            material = TaskMaterial(
                                task_id=new_task.id,
                                type="link",
                                name="\u0423\u044f\u0437\u0432\u0438\u043c\u0430\u044f \u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0430",
                                description="\u0412\u0435\u0431-\u0441\u0442\u0440\u0430\u043d\u0438\u0446\u0430 \u0441 XSS \u0443\u044f\u0437\u0432\u0438\u043c\u043e\u0441\u0442\u044c\u044e",
                                meta={"target_url": artifact["file_url"]},
                            )
                            db.add(material)

                        # \u0421\u043e\u0445\u0440\u0430\u043d\u0438\u0442\u044c ID \u0437\u0430\u0434\u0430\u0447\u0438 \u0432 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u0435 \u0434\u043b\u044f \u0441\u0441\u044b\u043b\u043a\u0438
                        best_variant.published_task_id = new_task.id

                        logger.info(
                            "\u0410\u0432\u0442\u043e\u043f\u0443\u0431\u043b\u0438\u043a\u043e\u0432\u0430\u043d\u043d\u0430\u044f UGC \u0437\u0430\u0434\u0430\u0447\u0430=%d \u0438\u0437 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u0430=%s",
                            new_task.id, best_variant.id,
                        )

                    await db.commit()

                    # \u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0437\u0430\u043f\u0440\u043e\u0441 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f
                    await _update_request_status(
                        db, request_id, "completed",
                        variant_id=best_variant.id,
                    )

                    logger.info(
                        "\u041a\u043e\u043d\u0432\u0435\u0439\u0435\u0440 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u0430 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u0412\u042b\u041f\u041e\u041b\u041d\u0415\u041d \u0437\u0430\u043f\u0440\u043e\u0441=%s \u0432\u044b\u0431\u0440\u0430\u043d=%s \u0432\u043e\u0437\u043d\u0430\u0433\u0440\u0430\u0436\u0434\u0435\u043d\u0438\u0435=%.3f",
                        request_id, best_variant.id, best_reward.total_reward,
                    )
                    return

            # \u0412\u0441\u0435 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u043d\u0435 \u043f\u0440\u043e\u0448\u043b\u0438 \u0438\u043b\u0438 \u043d\u0438\u0436\u0435 \u043f\u043e\u0440\u043e\u0433\u0430
            failure_reasons = []
            for vr in variant_rewards:
                if not vr.passed_all_binary:
                    failed = [c for c in vr.checks if c.score < 1.0 and c.is_binary()]
                    failure_reasons.extend(f"{c.type.value}: {c.detail}" for c in failed)

            # \u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0441\u0442\u0430\u0442\u0443\u0441 \u043f\u0430\u043a\u0435\u0442\u0430
            batch.status = "failed"
            batch.current_stage = "failed"
            batch.failure_reasons_summary = {"failure_context": failure_reasons[:10]}
            from datetime import datetime, timezone
            batch.completed_at = datetime.now(timezone.utc)
            await db.commit()

            await _update_request_status(
                db, request_id, "failed",
                failure_reason="\u0412\u0441\u0435 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u044b \u043d\u0435 \u043f\u0440\u043e\u0448\u043b\u0438 \u0434\u0432\u043e\u0438\u0447\u043d\u044b\u0435 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0438 \u0438\u043b\u0438 \u043d\u0438\u0436\u0435 \u043f\u043e\u0440\u043e\u0433\u0430; " + "; ".join(failure_reasons[:3]),
            )
            logger.warning(
                "\u041a\u043e\u043d\u0432\u0435\u0439\u0435\u0440 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u0430 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f \u041d\u0415 \u041f\u0420\u041e\u0419\u0414\u0415\u041d \u0437\u0430\u043f\u0440\u043e\u0441=%s \u0441\u043a\u043e\u0440\u043e\u0441\u0442\u044c_\u043f\u0440\u043e\u0445\u043e\u0436\u0434\u0435\u043d\u0438\u044f=%.0f%%",
                request_id, (len(passed) / max(len(variant_rewards), 1)) * 100,
            )

        except Exception as exc:
            logger.exception("\u041e\u0448\u0438\u0431\u043a\u0430 \u043a\u043e\u043d\u0432\u0435\u0439\u0435\u0440\u0430 \u0432\u0430\u0440\u0438\u0430\u043d\u0442\u0430 \u043f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044f")

            # \u041e\u0431\u043d\u043e\u0432\u0438\u0442\u044c \u0441\u0442\u0430\u0442\u0443\u0441 \u043f\u0430\u043a\u0435\u0442\u0430 \u043f\u0440\u0438 \u043e\u0448\u0438\u0431\u043a\u0435
            try:
                batch_result = await db.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == batch_id))
                batch = batch_result.scalar_one_or_none()
                if batch:
                    batch.status = "failed"
                    batch.current_stage = "failed"
                    batch.failure_reasons_summary = {"error": str(exc)}
                    from datetime import datetime, timezone
                    batch.completed_at = datetime.now(timezone.utc)
                    await db.commit()
            except Exception:
                pass  # \u0418\u0433\u043d\u043e\u0440\u0438\u0440\u043e\u0432\u0430\u0442\u044c \u043e\u0448\u0438\u0431\u043a\u0438 \u043e\u0431\u043d\u043e\u0432\u043b\u0435\u043d\u0438\u044f \u043f\u0430\u043a\u0435\u0442\u0430
            
            await _update_request_status(
                db, request_id, "failed",
                failure_reason=f"Pipeline error: {exc}",
            )


async def _failed_artifact(error: Optional[str]) -> ArtifactResult:
    """Создать неудачный результат артефакта."""
    return ArtifactResult(error=error or "generation failed")
