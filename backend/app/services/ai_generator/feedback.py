"""
Строитель контекста обратной связи для GRPO-пайплайна.

Запрашивает исторические ai_generation_variants для формирования few-shot контекста:
- positive_examples: лучшие варианты по quality_score (passed_all_binary=True)
  — вставляются как "вот как выглядит хорошее задание"
- negative_patterns: самые частые причины отказа
  — вставляются как "избегай этих ошибок"
- best_temperature: температура, дающая исторически лучшее качество
- recent_pass_rate: общий процент успеха для данного task_type/difficulty
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_generation import AIGenerationBatch, AIGenerationVariant

logger = logging.getLogger(__name__)

_MAX_POSITIVE = 3
_MAX_NEGATIVE = 5
_MIN_QUALITY_FOR_POSITIVE = 0.65
_RECENT_VARIANTS_SAMPLE = 50  # сколько недавних ошибок сканировать для поиска закономерностей
_MAX_USED_FLAGS = 80           # все ранее сгенерированные флаги для этого task_type
_MAX_USED_SCENARIOS = 30       # недавние названия сценариев для обеспечения разнообразия


@dataclass
class FeedbackContext:
    positive_examples: list[dict] = field(default_factory=list)
    negative_patterns: list[str] = field(default_factory=list)
    used_flags: list[str] = field(default_factory=list)
    used_scenario_titles: list[str] = field(default_factory=list)
    best_temperature: Optional[float] = None
    recent_pass_rate: Optional[float] = None

    def is_empty(self) -> bool:
        return (
            not self.positive_examples
            and not self.negative_patterns
            and not self.used_flags
            and not self.used_scenario_titles
        )

    def format_for_prompt(self) -> str:
        """Форматирует данные в текстовый блок для вставки в системный/пользовательский промпт."""
        if self.is_empty():
            return ""

        parts: list[str] = []

        # Жесткие ограничения сначала — модель должна видеть их раньше всего
        if self.used_flags:
            parts.append("## ЗАПРЕЩЁННЫЕ ФЛАГИ — нельзя использовать ни один")
            parts.append(", ".join(self.used_flags))
            parts.append("")

        if self.used_scenario_titles:
            parts.append("## УЖЕ СУЩЕСТВУЮЩИЕ СЦЕНАРИИ — создай ПРИНЦИПИАЛЬНО ДРУГОЙ")
            for title in self.used_scenario_titles:
                parts.append(f"- {title}")
            parts.append("")

        if self.positive_examples:
            parts.append("## Примеры удачных заданий (ориентируйся на эту структуру и качество)")
            for ex in self.positive_examples:
                q = ex.get("quality_score", 0.0)
                adv = ex.get("advantage", 0.0)
                parts.append(f"\n### Пример (quality={q:.2f}, advantage={adv:.3f})")
                spec = ex.get("spec", {})
                if spec.get("title"):
                    parts.append(f"Название: {spec['title']}")
                if spec.get("description"):
                    parts.append(f"Описание: {spec['description'][:300]}...")
                if spec.get("writeup"):
                    parts.append(f"Writeup (начало): {spec['writeup'][:200]}...")
                qd = ex.get("quality_details") or {}
                edu = qd.get("educational_value")
                if edu is not None:
                    parts.append(f"educational_value оценка: {edu:.2f}")
            parts.append("")

        if self.negative_patterns:
            parts.append("## Частые ошибки — ИЗБЕГАЙ этих паттернов")
            for reason in self.negative_patterns:
                parts.append(f"- {reason}")
            parts.append("")

        return "\n".join(parts)


async def compute_feedback_context(
    task_type: str,
    difficulty: str,
    db: AsyncSession,
) -> FeedbackContext:
    """
    Строит FeedbackContext из исторических данных генерации.

    Возвращает пустой FeedbackContext (без исключения), если БД пуста или запрос не удался.
    """
    ctx = FeedbackContext()
    try:
        await _load_used_flags(ctx, task_type, db)
        await _load_used_scenario_titles(ctx, task_type, db)
        await _load_positive_examples(ctx, task_type, difficulty, db)
        await _load_negative_patterns(ctx, task_type, difficulty, db)
        await _load_best_temperature(ctx, task_type, db)
        await _load_pass_rate(ctx, task_type, difficulty, db)
    except Exception as exc:
        logger.warning("compute_feedback_context failed: %s", exc)
    return ctx


async def _load_positive_examples(
    ctx: FeedbackContext,
    task_type: str,
    difficulty: str,
    db: AsyncSession,
) -> None:
    query = (
        select(AIGenerationVariant)
        .join(AIGenerationBatch, AIGenerationVariant.batch_id == AIGenerationBatch.id)
        .where(AIGenerationBatch.task_type == task_type)
        .where(AIGenerationBatch.difficulty == difficulty)
        .where(AIGenerationVariant.passed_all_binary == True)  # noqa: E712
        .where(AIGenerationVariant.quality_score >= _MIN_QUALITY_FOR_POSITIVE)
        .order_by(AIGenerationVariant.quality_score.desc())
        .limit(_MAX_POSITIVE)
    )
    result = await db.execute(query)
    for v in result.scalars().all():
        spec = v.generated_spec or {}
        # Убираем флаг, чтобы он не попал в будущие промпты
        safe_spec = {k: val for k, val in spec.items() if k != "flag"}
        ctx.positive_examples.append({
            "quality_score": v.quality_score or 0.0,
            "advantage": v.advantage or 0.0,
            "spec": safe_spec,
            "quality_details": v.quality_details,
        })


async def _load_negative_patterns(
    ctx: FeedbackContext,
    task_type: str,
    difficulty: str,
    db: AsyncSession,
) -> None:
    query = (
        select(AIGenerationVariant.failure_reason)
        .join(AIGenerationBatch, AIGenerationVariant.batch_id == AIGenerationBatch.id)
        .where(AIGenerationBatch.task_type == task_type)
        .where(AIGenerationBatch.difficulty == difficulty)
        .where(AIGenerationVariant.passed_all_binary == False)  # noqa: E712
        .where(AIGenerationVariant.failure_reason.isnot(None))
        .order_by(AIGenerationVariant.created_at.desc())
        .limit(_RECENT_VARIANTS_SAMPLE)
    )
    result = await db.execute(query)
    failure_reasons = [row[0] for row in result.fetchall() if row[0]]

    # Сгруппировать по сокращенному тексту причины и подсчитать частоту
    reason_counts: dict[str, int] = {}
    for reason in failure_reasons:
        key = reason[:150]
        reason_counts[key] = reason_counts.get(key, 0) + 1

    top = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)
    ctx.negative_patterns = [reason for reason, _ in top[:_MAX_NEGATIVE]]


async def _load_best_temperature(
    ctx: FeedbackContext,
    task_type: str,
    db: AsyncSession,
) -> None:
    query = (
        select(
            AIGenerationVariant.temperature,
            func.avg(AIGenerationVariant.quality_score).label("avg_quality"),
        )
        .join(AIGenerationBatch, AIGenerationVariant.batch_id == AIGenerationBatch.id)
        .where(AIGenerationBatch.task_type == task_type)
        .where(AIGenerationVariant.quality_score.isnot(None))
        .group_by(AIGenerationVariant.temperature)
        .order_by(text("avg_quality DESC"))
        .limit(1)
    )
    result = await db.execute(query)
    row = result.fetchone()
    if row:
        ctx.best_temperature = row[0]


async def _load_used_flags(
    ctx: FeedbackContext,
    task_type: str,
    db: AsyncSession,
) -> None:
    """
    Собрать все флаги, когда-либо сгенерированные для этого task_type.
    Внедрено как жесткое ограничение, чтобы модель никогда не повторила флаг.
    Охватывает неудачные варианты тоже — повторение плохо независимо от публикации задания.
    """
    query = (
        select(AIGenerationVariant.generated_spec["flag"].astext)
        .join(AIGenerationBatch, AIGenerationVariant.batch_id == AIGenerationBatch.id)
        .where(AIGenerationBatch.task_type == task_type)
        .where(AIGenerationVariant.generated_spec["flag"].astext.isnot(None))
        .distinct()
        .limit(_MAX_USED_FLAGS)
    )
    result = await db.execute(query)
    ctx.used_flags = [row[0] for row in result.fetchall() if row[0]]


async def _load_used_scenario_titles(
    ctx: FeedbackContext,
    task_type: str,
    db: AsyncSession,
) -> None:
    """
    Собрать недавние названия сценариев для этого task_type для обеспечения разнообразия.
    Включает только варианты, прошедшие двоичные проверки (названия низкого качества исключены).
    """
    query = (
        select(AIGenerationVariant.generated_spec["title"].astext)
        .join(AIGenerationBatch, AIGenerationVariant.batch_id == AIGenerationBatch.id)
        .where(AIGenerationBatch.task_type == task_type)
        .where(AIGenerationVariant.passed_all_binary == True)  # noqa: E712
        .where(AIGenerationVariant.generated_spec["title"].astext.isnot(None))
        .distinct()
        .limit(_MAX_USED_SCENARIOS)
    )
    result = await db.execute(query)
    ctx.used_scenario_titles = [row[0] for row in result.fetchall() if row[0]]


async def _load_pass_rate(
    ctx: FeedbackContext,
    task_type: str,
    difficulty: str,
    db: AsyncSession,
) -> None:
    base = (
        select(func.count())
        .select_from(AIGenerationVariant)
        .join(AIGenerationBatch, AIGenerationVariant.batch_id == AIGenerationBatch.id)
        .where(AIGenerationBatch.task_type == task_type)
        .where(AIGenerationBatch.difficulty == difficulty)
    )
    total = (await db.execute(base)).scalar() or 0
    if total == 0:
        return

    passed = (
        await db.execute(
            base.where(AIGenerationVariant.passed_all_binary == True)  # noqa: E712
        )
    ).scalar() or 0
    ctx.recent_pass_rate = passed / total
