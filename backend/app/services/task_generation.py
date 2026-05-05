import asyncio
import json
from typing import Any, Optional

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services.prompt_loader import load_prompt_text, PromptLoadError


class TaskGenerationError(RuntimeError):
    pass


TASK_MODEL_REGISTRY: dict[str, Any] = {
    "deepseek": lambda folder: f"gpt://{folder}/deepseek-v32/latest",
    "qwen": lambda _: "gpt://b1goei423tq1phl6o0av/qwen3.5-35b-a3b-fp8/latest",
    "qwen3": lambda _: "gpt://b1goei423tq1phl6o0av/qwen3.6-35b-a3b/latest",
}
DEFAULT_TASK_MODEL_KEY = "deepseek"


async def get_active_task_model_key(db: AsyncSession) -> str:
    from app.models.contest import PromptTemplate
    try:
        row = (
            await db.execute(select(PromptTemplate).where(PromptTemplate.code == "task_model"))
        ).scalar_one_or_none()
    except ProgrammingError:
        await db.rollback()
        return DEFAULT_TASK_MODEL_KEY
    if row and (row.content or "").strip() in TASK_MODEL_REGISTRY:
        return row.content.strip()
    return DEFAULT_TASK_MODEL_KEY


def _load_system_prompt() -> str:
    try:
        return load_prompt_text("task_prompt.txt")
    except PromptLoadError as exc:
        raise TaskGenerationError(str(exc)) from exc


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
        raise TaskGenerationError(f"Missing Yandex LLM config: {', '.join(missing)}")
    return OpenAI(
        api_key=api_key,
        base_url="https://llm.api.cloud.yandex.net/v1",
        project=folder,
    )


def _run_generation(
    difficulty: int,
    tags: list[str],
    description: str,
    system_prompt: Optional[str] = None,
    model_uri: Optional[str] = None,
) -> dict[str, Any]:
    prompt_text = (system_prompt or "").strip() or _load_system_prompt()
    client = _build_client()
    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    if not model_uri:
        model_uri = TASK_MODEL_REGISTRY[DEFAULT_TASK_MODEL_KEY](folder)
    reasoning_effort = settings.YANDEX_REASONING_EFFORT or "high"
    user_payload = {
        "difficulty": difficulty,
        "tags": tags,
        "description": description,
    }
    try:
        response = client.chat.completions.create(
            model=model_uri,
            reasoning_effort=reasoning_effort,
            messages=[
                {"role": "system", "content": prompt_text},
                {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
            ],
        )
    except Exception as exc:  # noqa: BLE001
        raise TaskGenerationError(f"Yandex model request failed: {exc}") from exc
    text = (response.choices[0].message.content or "").strip()
    cleaned = _strip_code_fence(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise TaskGenerationError(f"Model returned invalid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise TaskGenerationError(
            f"Model returned JSON root type '{type(parsed).__name__}', expected object"
        )
    return {
        "model": model_uri,
        "reasoning_effort": reasoning_effort,
        "raw_text": text,
        "parsed": parsed,
        "input": user_payload,
    }


async def generate_task_payload(
    difficulty: int,
    tags: list[str],
    description: str,
    model_uri: Optional[str] = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(_run_generation, difficulty, tags, description, None, model_uri)


async def generate_task_payload_with_prompt(
    difficulty: int,
    tags: list[str],
    description: str,
    system_prompt: str,
    model_uri: Optional[str] = None,
) -> dict[str, Any]:
    return await asyncio.to_thread(_run_generation, difficulty, tags, description, system_prompt, model_uri)
