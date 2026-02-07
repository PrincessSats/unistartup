import asyncio
import json
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import settings


class TaskGenerationError(RuntimeError):
    pass


def _find_prompt_path() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        candidate = parent / "task_prompt.txt"
        if candidate.exists():
            return candidate
    raise TaskGenerationError("task_prompt.txt not found")


def _load_system_prompt() -> str:
    path = _find_prompt_path()
    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise TaskGenerationError("task_prompt.txt is empty")
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
        raise TaskGenerationError("Missing YANDEX_CLOUD_API_KEY or YANDEX_CLOUD_FOLDER")
    return OpenAI(
        api_key=settings.YANDEX_CLOUD_API_KEY,
        base_url="https://llm.api.cloud.yandex.net/v1",
        project=settings.YANDEX_CLOUD_FOLDER,
    )


def _run_generation(difficulty: int, tags: list[str], description: str) -> dict[str, Any]:
    system_prompt = _load_system_prompt()
    client = _build_client()
    model_name = f"gpt://{settings.YANDEX_CLOUD_FOLDER}/qwen3-235b-a22b-fp8/latest"
    user_payload = {
        "difficulty": difficulty,
        "tags": tags,
        "description": description,
    }
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    cleaned = _strip_code_fence(text)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise TaskGenerationError(f"Model returned invalid JSON: {exc}") from exc
    return {
        "model": model_name,
        "raw_text": text,
        "parsed": parsed,
        "input": user_payload,
    }


async def generate_task_payload(difficulty: int, tags: list[str], description: str) -> dict[str, Any]:
    return await asyncio.to_thread(_run_generation, difficulty, tags, description)
