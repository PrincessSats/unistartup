from __future__ import annotations

from importlib import resources
from pathlib import Path

from app.config import settings


class PromptLoadError(RuntimeError):
    pass


def _read_prompt_file(path: Path, filename: str) -> str:
    candidate = path / filename
    if not candidate.exists() or not candidate.is_file():
        return ""
    content = candidate.read_text(encoding="utf-8").strip()
    if not content:
        raise PromptLoadError(f"{filename} is empty: {candidate}")
    return content


def load_prompt_text(filename: str) -> str:
    # 1) Explicit directory override.
    if settings.PROMPTS_DIR:
        content = _read_prompt_file(Path(settings.PROMPTS_DIR).expanduser(), filename)
        if content:
            return content

    # 2) Packaged prompt bundled with backend app.
    try:
        content = resources.files("app.prompts").joinpath(filename).read_text(encoding="utf-8").strip()
    except (FileNotFoundError, ModuleNotFoundError):
        content = ""
    if content:
        return content

    # 3) Legacy fallback paths for local/dev compatibility.
    current = Path(__file__).resolve()
    legacy_dirs = [
        current.parent,               # backend/app/services
        current.parent.parent,        # backend/app
        current.parent.parent.parent, # backend
        current.parent.parent.parent.parent, # repo root
    ]
    for directory in legacy_dirs:
        content = _read_prompt_file(directory, filename)
        if content:
            return content

    raise PromptLoadError(f"{filename} not found. Set PROMPTS_DIR or include it in app.prompts package.")
