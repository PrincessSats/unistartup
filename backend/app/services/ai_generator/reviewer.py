"""
LLM-as-judge quality reviewer for AI-generated CTF challenges.

Scores 5 dimensions (0.0-1.0 each) and returns the average as composite quality_score.
Only called for variants that already passed all binary reward checks.
"""
import json
import logging
from typing import Optional

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

REVIEWER_MODEL_ID = "deepseek-v32"
REVIEWER_MODEL_VERSION = "latest"

_reviewer_client: Optional[AsyncOpenAI] = None

QUALITY_DIMENSIONS = [
    "educational_value",
    "scenario_realism",
    "hint_quality",
    "writeup_clarity",
    "difficulty_calibration",
]

REVIEWER_SYSTEM_PROMPT = """\
You are an expert CTF challenge quality evaluator. Given a CTF challenge spec, \
score each dimension from 0.0 to 1.0 with one decimal place.

Respond ONLY with valid JSON matching this exact schema:
{
  "educational_value": <float 0.0-1.0>,
  "scenario_realism": <float 0.0-1.0>,
  "hint_quality": <float 0.0-1.0>,
  "writeup_clarity": <float 0.0-1.0>,
  "difficulty_calibration": <float 0.0-1.0>,
  "reasoning": "<one sentence>"
}

Scoring guide:
- educational_value: Does solving this teach real security skills?
- scenario_realism: Is the challenge scenario plausible in the real world?
- hint_quality: Are hints graduated and helpful without giving away the answer?
- writeup_clarity: Is the writeup explanation clear and educational?
- difficulty_calibration: Does the challenge match the stated difficulty level?
"""


class ReviewerError(RuntimeError):
    pass


def _build_reviewer_client() -> AsyncOpenAI:
    global _reviewer_client
    api_key = (settings.YANDEX_CLOUD_API_KEY or "").strip()
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    missing: list[str] = []
    if not api_key:
        missing.append("YANDEX_CLOUD_API_KEY (or YANDEX_API_KEY / YC_API_KEY)")
    if not folder:
        missing.append("YANDEX_CLOUD_FOLDER (or YANDEX_CLOUD_FOLDER_ID / YANDEX_FOLDER_ID)")
    if missing:
        raise ReviewerError(f"Missing Yandex LLM config: {', '.join(missing)}")
    if _reviewer_client is None:
        _reviewer_client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://ai.api.cloud.yandex.net/v1",
            project=folder,
        )
    return _reviewer_client


async def review_variant(spec: dict, task_type: str, difficulty: str) -> tuple[float, dict]:
    """
    Score a variant spec using LLM-as-judge.

    Returns:
        (quality_score, quality_details) where quality_score is the average of all dimensions.
    """
    client = _build_reviewer_client()
    folder = settings.YANDEX_CLOUD_FOLDER.strip()
    model = f"gpt://{folder}/{REVIEWER_MODEL_ID}/{REVIEWER_MODEL_VERSION}"

    user_content = (
        f"task_type: {task_type}\n"
        f"difficulty: {difficulty}\n\n"
        f"Challenge spec:\n{json.dumps(spec, ensure_ascii=False, indent=2)}"
    )

    try:
        response = await client.chat.completions.create(
            model=model,
            temperature=0.1,
            messages=[
                {"role": "system", "content": REVIEWER_SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            max_tokens=512,
        )
    except Exception as exc:
        logger.warning("Reviewer LLM call failed: %s", exc)
        return 0.0, {"error": str(exc)}

    raw = ""
    try:
        raw = response.choices[0].message.content or ""
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
