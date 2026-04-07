import asyncio
import json
import logging
from typing import Any, Optional

from openai import OpenAI

from app.config import settings
from app.services.prompt_loader import load_prompt_text, PromptLoadError


class ArticleGenerationError(RuntimeError):
    pass


logger = logging.getLogger(__name__)


def _load_system_prompt() -> str:
    try:
        return load_prompt_text("article_prompt.txt")
    except PromptLoadError as exc:
        raise ArticleGenerationError(str(exc)) from exc


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
    api_key = (settings.YANDEX_CLOUD_API_KEY or "").strip()
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    missing: list[str] = []
    if not api_key:
        missing.append("YANDEX_CLOUD_API_KEY (or YANDEX_API_KEY / YC_API_KEY)")
    if not folder:
        missing.append("YANDEX_CLOUD_FOLDER (or YANDEX_CLOUD_FOLDER_ID / YANDEX_FOLDER_ID / YC_FOLDER_ID)")
    if missing:
        raise ArticleGenerationError(f"Missing Yandex LLM config: {', '.join(missing)}")
    return OpenAI(
        api_key=api_key,
        base_url="https://llm.api.cloud.yandex.net/v1",
        project=folder,
        timeout=120,
    )


def _run_generation(raw_en_text: str, system_prompt: Optional[str] = None) -> dict[str, Any]:
    prompt_text = (system_prompt or "").strip() or _load_system_prompt()
    client = _build_client()
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    model_name = f"gpt://{folder}/deepseek-v32/latest"
    reasoning_effort = settings.YANDEX_REASONING_EFFORT or "high"
    logger.info(
        "KB generation started (model=%s, reasoning_effort=%s, chars=%s)",
        model_name,
        reasoning_effort,
        len(raw_en_text),
    )
    try:
        response = client.chat.completions.create(
            model=model_name,
            reasoning_effort=reasoning_effort,
            messages=[
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": raw_en_text},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Yandex LLM request failed (type=%s): %s",
            type(exc).__name__, exc,
        )
        raise ArticleGenerationError(f"Yandex model request failed: {exc}") from exc
    text = (response.choices[0].message.content or "").strip()
    logger.info("KB generation completed (chars=%s)", len(text))
    cleaned = _strip_code_fence(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.error(
            "Model returned invalid JSON (chars=%d, preview=%r): %s",
            len(text), text[:300], exc,
        )
        raise ArticleGenerationError(f"Model returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ArticleGenerationError(
            f"Model returned JSON root type '{type(parsed).__name__}', expected object"
        )
    return {
        "model": model_name,
        "reasoning_effort": reasoning_effort,
        "raw_text": text,
        "parsed": parsed,
        "input": {"raw_en_text": raw_en_text},
    }


async def generate_article_payload(raw_en_text: str) -> dict[str, Any]:
    return await asyncio.to_thread(_run_generation, raw_en_text)


async def generate_article_payload_with_prompt(raw_en_text: str, system_prompt: str) -> dict[str, Any]:
    return await asyncio.to_thread(_run_generation, raw_en_text, system_prompt)
