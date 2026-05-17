import asyncio
import json
import logging
from datetime import date

from sqlalchemy import text

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.contest import KBEntry, Task
from app.services.article_generation import generate_article_payload_with_prompt, ArticleGenerationError
from app.services.nvd_sync import run_sync
from app.services.prompt_loader import load_prompt_text, PromptLoadError
from app.services.task_generation import (
    TASK_MODEL_REGISTRY,
    TaskGenerationError,
    generate_task_payload,
    get_active_task_model_key,
)

logger = logging.getLogger(__name__)

_TOP_CVE_HOURS = 24
_TOP_CVE_SQL = """
    SELECT id, cve_id, ru_title, ru_summary, cvss_base_score, tags, difficulty
    FROM kb_entries
    WHERE source = 'nvd'
      AND ru_title IS NOT NULL
      AND length(trim(ru_title)) > 0
      AND created_at >= now() - (:hours_interval)::interval
    ORDER BY cvss_base_score DESC NULLS LAST, created_at DESC
    LIMIT :limit
"""

_ALREADY_DONE_SQL = """
    SELECT 1 FROM kb_entries
    WHERE source = 'digest'
      AND created_at >= now() - interval '20 hours'
    LIMIT 1
"""


async def _is_recently_completed() -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(_ALREADY_DONE_SQL))
        return result.scalar() is not None


async def _select_top_cves(hours: int = _TOP_CVE_HOURS, limit: int = 10) -> list:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            text(_TOP_CVE_SQL),
            {"hours_interval": f"{hours} hours", "limit": limit},
        )
        return result.mappings().all()


async def _generate_digest(top_entries: list) -> int | None:
    if not top_entries:
        logger.warning("daily_pipeline: no top CVEs found, skipping digest")
        return None

    try:
        prompt_text = load_prompt_text("digest_prompt.txt")
    except PromptLoadError as exc:
        logger.error("daily_pipeline: failed to load digest_prompt.txt: %s", exc)
        return None

    input_rows = [
        {
            "cve_id": row["cve_id"],
            "ru_title": row["ru_title"],
            "ru_summary": row["ru_summary"],
            "cvss_base_score": row["cvss_base_score"],
        }
        for row in top_entries
    ]
    input_text = json.dumps(input_rows, ensure_ascii=False)

    try:
        result = await generate_article_payload_with_prompt(input_text, prompt_text)
    except ArticleGenerationError as exc:
        logger.error("daily_pipeline: digest LLM call failed: %s", exc)
        return None

    parsed = result.get("parsed", {})
    ru_title = parsed.get("ru_title") or f"Дайджест угроз {date.today().isoformat()}"
    ru_summary = parsed.get("ru_summary") or ""
    ru_explainer = parsed.get("ru_explainer") or ""
    tags = parsed.get("tags") or ["cve", "digest"]
    referenced_cve_ids = parsed.get("referenced_cve_ids") or [
        r["cve_id"] for r in input_rows if r.get("cve_id")
    ]

    async with AsyncSessionLocal() as session:
        entry = KBEntry(
            source="digest",
            source_id=f"digest-{date.today().isoformat()}",
            cve_id=None,
            raw_en_text=input_text,
            ru_title=ru_title,
            ru_summary=ru_summary,
            ru_explainer=ru_explainer,
            tags=tags,
            difficulty=None,
            referenced_cve_ids=referenced_cve_ids,
        )
        session.add(entry)
        try:
            await session.commit()
            await session.refresh(entry)
            logger.info("daily_pipeline: digest created id=%s", entry.id)
            return entry.id
        except Exception as exc:
            await session.rollback()
            logger.error("daily_pipeline: failed to save digest: %s", exc)
            return None


async def _generate_one_task(entry: dict, model_uri: str, semaphore: asyncio.Semaphore) -> dict | None:
    difficulty = entry.get("difficulty")
    try:
        difficulty = int(difficulty) if difficulty is not None else 5
    except (TypeError, ValueError):
        difficulty = 5
    difficulty = max(1, min(10, difficulty))

    tags = list(entry.get("tags") or [])
    description = entry.get("ru_summary") or entry.get("cve_id") or ""

    async with semaphore:
        try:
            return await generate_task_payload(difficulty, tags, description, model_uri)
        except TaskGenerationError as exc:
            logger.error("daily_pipeline: task generation failed for cve=%s: %s", entry.get("cve_id"), exc)
            return None


async def _generate_tasks_for_top(top_entries: list) -> list[int]:
    if not top_entries:
        return []

    async with AsyncSessionLocal() as session:
        model_key = await get_active_task_model_key(session)

    folder = (settings.YANDEX_CLOUD_FOLDER or "").strip()
    model_uri = TASK_MODEL_REGISTRY[model_key](folder)
    semaphore = asyncio.Semaphore(settings.DAILY_PIPELINE_CONCURRENCY)

    results = await asyncio.gather(
        *[_generate_one_task(entry, model_uri, semaphore) for entry in top_entries],
        return_exceptions=False,
    )

    task_ids: list[int] = []
    async with AsyncSessionLocal() as session:
        for entry, result in zip(top_entries, results):
            if result is None:
                continue
            parsed = result.get("parsed", {})
            title = (parsed.get("title") or "").strip() or f"CVE Task: {entry.get('cve_id', 'unknown')}"
            category = (parsed.get("category") or "misc").strip()

            try:
                difficulty = int(parsed.get("difficulty") or entry.get("difficulty") or 5)
                difficulty = max(1, min(10, difficulty))
            except (TypeError, ValueError):
                difficulty = 5

            try:
                points = int(parsed.get("points") or 100 + (difficulty - 1) * 50)
            except (TypeError, ValueError):
                points = 100 + (difficulty - 1) * 50

            task = Task(
                title=title,
                category=category,
                difficulty=difficulty,
                points=points,
                tags=parsed.get("tags") or list(entry.get("tags") or []),
                language=parsed.get("language") or "ru",
                story=parsed.get("story"),
                participant_description=parsed.get("participant_description"),
                state="draft",
                task_kind="practice",
                access_type="just_flag",
                kb_entry_id=entry["id"],
                llm_raw_response=result["parsed"],
                created_by=None,
            )
            session.add(task)
            try:
                await session.flush()
                task_ids.append(task.id)
            except Exception as exc:
                await session.rollback()
                logger.error("daily_pipeline: failed to save task for cve=%s: %s", entry.get("cve_id"), exc)
                continue

        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error("daily_pipeline: batch task commit failed: %s", exc)
            return []

    logger.info("daily_pipeline: created %d draft tasks", len(task_ids))
    return task_ids


async def run_daily_pipeline(*, force: bool = False) -> dict:
    if not force and await _is_recently_completed():
        logger.info("daily_pipeline: already completed in last 20h, skipping")
        return {"status": "already_done"}

    logger.info("daily_pipeline: starting NVD sync")
    try:
        sync_result = await run_sync(
            hours=_TOP_CVE_HOURS,
            embed_new_entries=True,
            translate_new_entries=True,
        )
        logger.info(
            "daily_pipeline: sync done fetched=%s inserted=%s",
            sync_result.get("fetched"),
            sync_result.get("inserted"),
        )
    except Exception as exc:
        logger.error("daily_pipeline: NVD sync failed: %s", exc)
        return {"status": "error", "stage": "nvd_sync", "error": str(exc)}

    if not settings.DAILY_DIGEST_ENABLED:
        return {"status": "done", "sync": sync_result, "digest_id": None, "task_ids": []}

    top_entries = await _select_top_cves(hours=_TOP_CVE_HOURS, limit=settings.DAILY_TASK_COUNT)
    logger.info("daily_pipeline: selected %d top CVEs", len(top_entries))

    digest_id = await _generate_digest(top_entries)
    task_ids = await _generate_tasks_for_top(top_entries)

    return {
        "status": "done",
        "sync": {k: v for k, v in sync_result.items() if k != "inserted_rows"},
        "digest_id": digest_id,
        "task_count": len(task_ids),
    }
