"""Background runner for the standalone championship-task generation page.

Mirrors the NVD-sync pattern: an asyncio background task generates tasks one cluster at a
time, persisting per-task progress to the contest_gen_jobs row so the frontend can poll.
Generated tasks go to the draft pool (NOT attached to any contest). Within a single run,
themes are de-duplicated (no two tasks share a category).
"""
import asyncio
import logging
from typing import Any, Optional

from app.database import AsyncSessionLocal
from app.models.contest import ContestGenJob
from app.services.championship_generation import (
    ChampionshipGenerationError,
    generate_championship_task,
    materialize_championship_task,
    select_kb_entry_clusters,
)

logger = logging.getLogger(__name__)

# Keep strong refs so background tasks are not garbage-collected mid-flight.
_gen_background_tasks: set[asyncio.Task] = set()


def launch_generation_job(**kwargs) -> None:
    task = asyncio.create_task(run_generation_job(**kwargs))
    _gen_background_tasks.add(task)
    task.add_done_callback(_gen_background_tasks.discard)


async def run_generation_job(
    *,
    job_id: Any,
    mode: str,
    kb_entry_ids: Optional[list[int]],
    filters: Optional[dict],
    count: int,
    base_difficulty: int,
    system_prompt: str,
    model_uri: str,
    admin_id: Optional[int],
) -> None:
    async with AsyncSessionLocal() as db:
        job = await db.get(ContestGenJob, job_id)
        if job is None:
            logger.warning("Contest gen job %s not found", job_id)
            return

        # 1) Pick thematically distinct clusters (dedup within batch).
        try:
            clusters = await select_kb_entry_clusters(
                db,
                mode=mode,
                kb_entry_ids=kb_entry_ids,
                filters=filters,
                count=count,
                k_per_task=3,
                diversify=True,
            )
        except ChampionshipGenerationError as exc:
            job.status = "failed"
            job.error = str(exc)
            await db.commit()
            return

        events = [
            {"index": i, "status": "queued", "title": None, "category": None,
             "task_id": None, "error": None}
            for i in range(len(clusters))
        ]
        job.total = len(clusters)
        job.events = list(events)
        await db.commit()

        used_categories: set[str] = set()
        used_titles: set[str] = set()
        created: list[int] = []

        for idx, kb_entries in enumerate(clusters):
            events[idx]["status"] = "generating"
            job.events = list(events)
            await db.commit()

            try:
                result = await generate_championship_task(
                    kb_entries=kb_entries,
                    base_difficulty=base_difficulty,
                    system_prompt=system_prompt,
                    model_uri=model_uri,
                    avoid_categories=list(used_categories),
                    avoid_titles=list(used_titles),
                )
                task = await materialize_championship_task(
                    db,
                    result=result,
                    base_difficulty=base_difficulty,
                    created_by=admin_id,
                )
                await db.commit()

                created.append(task.id)
                used_categories.add(task.category)
                used_titles.add(task.title)
                events[idx].update(
                    status="done", title=task.title, category=task.category, task_id=task.id,
                )
                job.completed = len(created)
                job.created_task_ids = list(created)
                job.events = list(events)
                await db.commit()
            except Exception as exc:  # noqa: BLE001 — record per-task failure, keep going
                await db.rollback()
                logger.exception("Championship task generation failed (cluster %s)", idx)
                events[idx].update(status="failed", error=str(exc))
                job.failed = (job.failed or 0) + 1
                job.events = list(events)
                await db.commit()

        job.status = "failed" if (not created and job.failed) else "completed"
        await db.commit()
