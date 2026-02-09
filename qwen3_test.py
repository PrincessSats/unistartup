import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

YANDEX_CLOUD_API_KEY = os.getenv("YANDEX_CLOUD_API_KEY")
YANDEX_CLOUD_FOLDER = os.getenv("YANDEX_CLOUD_FOLDER")

if not YANDEX_CLOUD_API_KEY or not YANDEX_CLOUD_FOLDER:
    raise RuntimeError("Missing YANDEX_CLOUD_API_KEY or YANDEX_CLOUD_FOLDER in .env")

client = OpenAI(
    api_key=YANDEX_CLOUD_API_KEY,
    base_url="https://llm.api.cloud.yandex.net/v1",
    project=YANDEX_CLOUD_FOLDER,
)

with open("sys_prompt.txt", "r", encoding="utf-8") as f:
    system_prompt = f.read().strip()

if not system_prompt:
    raise RuntimeError("sys_prompt.txt is empty")


def _strip_code_fence(text: str) -> str:
    if not text.startswith("```"):
        return text
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    return "\n".join(lines).strip()


def _format_output(text: str) -> str:
    text = _strip_code_fence(text.strip())
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return text
    return json.dumps(parsed, ensure_ascii=False, indent=2)


def _load_tasks() -> list[tuple[str, str]]:
    tasks = []
    for idx in range(1, 11):
        name = f"task{idx}.json"
        with open(name, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            raise RuntimeError(f"{name} is empty")
        tasks.append((name, content))
    return tasks


model_name = f"gpt://{YANDEX_CLOUD_FOLDER}/qwen3-235b-a22b-fp8/latest"

for task_name, task_content in _load_tasks():
    response = client.chat.completions.create(
        model=model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task_content},
        ],
    )

    text = (response.choices[0].message.content or "").strip()
    formatted = _format_output(text)

    print(f"=== {task_name} ===")
    print(formatted)
    print()
