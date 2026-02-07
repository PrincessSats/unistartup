import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import settings


class ArticleGenerationError(RuntimeError):
    pass


logger = logging.getLogger(__name__)


def _find_prompt_path() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        candidate = parent / "article_prompt.txt"
        if candidate.exists():
            return candidate
    raise ArticleGenerationError("article_prompt.txt not found")


def _load_system_prompt() -> str:
    path = _find_prompt_path()
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ArticleGenerationError("article_prompt.txt is empty")
    return content


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _build_client() -> OpenAI:
    if not settings.YANDEX_CLOUD_API_KEY or not settings.YANDEX_CLOUD_FOLDER:
        raise ArticleGenerationError("Missing YANDEX_CLOUD_API_KEY or YANDEX_CLOUD_FOLDER")
    return OpenAI(
        api_key=settings.YANDEX_CLOUD_API_KEY,
        base_url="https://llm.api.cloud.yandex.net/v1",
        project=settings.YANDEX_CLOUD_FOLDER,
    )


def _run_generation(raw_en_text: str) -> dict[str, Any]:
    system_prompt = _load_system_prompt()
    client = _build_client()
    model_name = f"gpt://{settings.YANDEX_CLOUD_FOLDER}/qwen3-235b-a22b-fp8/latest"
    logger.info("KB generation started (model=%s, chars=%s)", model_name, len(raw_en_text))
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_en_text},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    logger.info("KB generation completed (chars=%s)", len(text))
    cleaned = _strip_code_fence(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ArticleGenerationError(f"Model returned invalid JSON: {exc}") from exc
    return {
        "model": model_name,
        "raw_text": text,
        "parsed": parsed,
        "input": {"raw_en_text": raw_en_text},
    }


async def generate_article_payload(raw_en_text: str) -> dict[str, Any]:
    return await asyncio.to_thread(_run_generation, raw_en_text)
