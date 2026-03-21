"""
LLM-as-judge quality reviewer for AI-generated CTF challenges.

Scores 5 dimensions (0.0-1.0 each) and returns the average as composite quality_score.
Only called for variants that already passed all binary reward checks.
"""
import asyncio
import json
import logging
from typing import Optional

from openai import OpenAI

from app.config import settings

logger = logging.getLogger(__name__)

REVIEWER_MODEL_ID = "deepseek-v32"
REVIEWER_MODEL_VERSION = "latest"

_reviewer_client: Optional[OpenAI] = None

QUALITY_DIMENSIONS = [
    "educational_value",
    "scenario_realism",
    "hint_quality",
    "writeup_clarity",
    "difficulty_calibration",
]

REVIEWER_SYSTEM_PROMPT = """\
Ты — эксперт по оценке качества CTF-заданий. Оцени предоставленный CTF challenge spec по 5 критериям.

КРИТИЧЕСКОЕ ТРЕБОВАНИЕ ВЫХОДА:
- Отвечай ТОЛЬКО валидным JSON (один объект), без Markdown, без пояснений, без текста до/после.
- Никаких комментариев, никаких trailing commas, только стандартный JSON.

ВЫХОДНОЙ JSON (ровно эти ключи):
{
  "educational_value": <float 0.0-1.0>,
  "scenario_realism": <float 0.0-1.0>,
  "hint_quality": <float 0.0-1.0>,
  "writeup_clarity": <float 0.0-1.0>,
  "difficulty_calibration": <float 0.0-1.0>,
  "reasoning": "<одно предложение — общий вывод>"
}

КРИТЕРИИ ОЦЕНКИ:
- educational_value: учит ли задание реальным навыкам безопасности?
- scenario_realism: реалистичен ли сценарий задания?
- hint_quality: подсказки дозированы и полезны, не раскрывают ответ?
- writeup_clarity: writeup понятен и полезен для обучения?
- difficulty_calibration: соответствует ли задание заявленному уровню сложности?
"""


class ReviewerError(RuntimeError):
    pass


def _build_reviewer_client() -> OpenAI:
    global _reviewer_client
    api_key = (settings.YANDEX_CLOUD_API_KEY or "").strip()
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    missing: list[str] = []
    if not api_key:
        missing.append("YANDEX_CLOUD_API_KEY")
    if not folder:
        missing.append("YANDEX_CLOUD_FOLDER")
    if missing:
        raise ReviewerError(f"Missing Yandex LLM config: {', '.join(missing)}")
    if _reviewer_client is None:
        _reviewer_client = OpenAI(
            api_key=api_key,
            base_url="https://llm.api.cloud.yandex.net/v1",
            project=folder,
        )
    return _reviewer_client


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _run_review(spec: dict, task_type: str, difficulty: str) -> tuple[float, dict]:
    client = _build_reviewer_client()
    folder = settings.YANDEX_CLOUD_FOLDER.strip()
    model = f"gpt://{folder}/{REVIEWER_MODEL_ID}/{REVIEWER_MODEL_VERSION}"
    reasoning_effort = settings.YANDEX_REASONING_EFFORT or "high"

    user_content = json.dumps({
        "task_type": task_type,
        "difficulty": difficulty,
        "spec": spec,
    }, ensure_ascii=False)

    try:
        response = client.chat.completions.create(
            model=model,
            reasoning_effort=reasoning_effort,
            messages=[
                {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
    except Exception as exc:
        logger.warning("Reviewer LLM call failed: %s", exc)
        return 0.0, {"error": str(exc)}

    raw = (response.choices[0].message.content or "").strip()
    raw = _strip_code_fence(raw)

    try:
        details = json.loads(raw)
    except Exception as exc:
        logger.warning("Reviewer response parse error: %s — raw=%r", exc, raw)
        return 0.0, {"error": str(exc), "raw": raw}

    scores = [
        float(details.get(dim, 0.0))
        for dim in QUALITY_DIMENSIONS
        if isinstance(details.get(dim), (int, float))
    ]
    if not scores:
        return 0.0, details

    quality_score = sum(scores) / len(scores)
    return round(quality_score, 3), details


async def review_variant(spec: dict, task_type: str, difficulty: str) -> tuple[float, dict]:
    """
    Score a variant spec using LLM-as-judge.
    Runs the sync OpenAI client in a thread to avoid blocking the event loop.
    """
    return await asyncio.to_thread(_run_review, spec, task_type, difficulty)
