from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import date, datetime, timezone

from sqlalchemy import select, text

from app.config import settings
from app.database import AsyncSessionLocal
from app.models.ai_generation import AIGenerationBatch, AIGenerationVariant
from app.models.contest import KBEntry, Task, TaskAuthorSolution, TaskFlag, TaskMaterial
from app.services.ai_generator.cwe_mapping import infer_task_type
from app.services.ai_generator.pipeline import run_pipeline
from app.services.article_generation import ArticleGenerationError, generate_article_payload_with_prompt
from app.services.nvd_sync import run_sync
from app.services.prompt_loader import PromptLoadError, load_prompt_text

logger = logging.getLogger(__name__)

RU_MONTHS = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

ACCESS_TYPE_MAP = {
    "crypto_text_web": "just_flag",
    "forensics_image_metadata": "file",
    "web_static_xss": "link",
    "chat_llm": "chat",
}
DIFFICULTY_INT_MAP = {"beginner": 1, "intermediate": 2, "advanced": 3}
DIFFICULTY_POINTS_MAP = {"beginner": 50, "intermediate": 100, "advanced": 200}

# Fixed 12-slot distribution: 4 per category, each with 2 easy + 1 intermediate + 1 hard.
# CVEs are assigned sequentially from the top-12 most interesting (highest CVSS).
_TASK_SLOTS: list[tuple[str, str]] = [
    ("web_static_xss",          "beginner"),
    ("web_static_xss",          "beginner"),
    ("web_static_xss",          "intermediate"),
    ("web_static_xss",          "advanced"),
    ("crypto_text_web",         "beginner"),
    ("crypto_text_web",         "beginner"),
    ("crypto_text_web",         "intermediate"),
    ("crypto_text_web",         "advanced"),
    ("forensics_image_metadata","beginner"),
    ("forensics_image_metadata","beginner"),
    ("forensics_image_metadata","intermediate"),
    ("forensics_image_metadata","advanced"),
]

# How many CVEs to send to digest LLM at most (keep prompt within context window).
_DIGEST_LLM_INPUT_CAP = 60

_ALREADY_DONE_SQL = """
    SELECT 1 FROM kb_entries
    WHERE source = 'digest'
      AND created_at >= now() - interval '20 hours'
    LIMIT 1
"""

_TODAY_ENTRIES_SQL = """
    SELECT id, cve_id, ru_title, ru_summary, cvss_base_score, tags, difficulty,
           cwe_ids, attack_vector
    FROM kb_entries
    WHERE source = 'nvd'
      AND created_at >= now() - interval '24 hours'
      AND ru_title IS NOT NULL
      AND length(trim(ru_title)) > 0
    ORDER BY cvss_base_score DESC NULLS LAST, created_at DESC
"""

_HIDE_NVD_SQL = """
    UPDATE kb_entries
    SET visible_in_kb_list = false
    WHERE source = 'nvd'
      AND visible_in_kb_list = true
"""


def _cvss_to_grpo_difficulty(cvss: float | None) -> str:
    if cvss is None or cvss < 4.0:
        return "beginner"
    if cvss < 7.0:
        return "intermediate"
    return "advanced"


async def _is_recently_completed() -> bool:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(_ALREADY_DONE_SQL))
        return result.scalar() is not None


async def _hide_all_nvd_entries() -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(_HIDE_NVD_SQL))
        await session.commit()
        return result.rowcount or 0


async def _select_today_entries() -> list:
    async with AsyncSessionLocal() as session:
        result = await session.execute(text(_TODAY_ENTRIES_SQL))
        return result.mappings().all()


async def _generate_digest(today_entries: list) -> int | None:
    if not today_entries:
        logger.warning("daily_pipeline: no today entries, skipping digest")
        return None

    try:
        prompt_text = load_prompt_text("digest_prompt.txt")
    except PromptLoadError as exc:
        logger.error("daily_pipeline: failed to load digest_prompt.txt: %s", exc)
        return None

    # All CVE IDs are referenced; LLM input is capped for context-size safety.
    all_cve_ids = [r["cve_id"] for r in today_entries if r.get("cve_id")]
    llm_input_rows = today_entries[:_DIGEST_LLM_INPUT_CAP]
    input_payload = [
        {
            "cve_id": r["cve_id"],
            "kb_id": r["id"],
            "ru_title": r["ru_title"],
            "cvss_base_score": r["cvss_base_score"],
        }
        for r in llm_input_rows
    ]
    input_text = json.dumps(input_payload, ensure_ascii=False)

    try:
        result = await generate_article_payload_with_prompt(input_text, prompt_text)
    except ArticleGenerationError as exc:
        logger.error("daily_pipeline: digest LLM call failed: %s", exc)
        return None

    parsed = result.get("parsed", {})
    today = date.today()
    subject = (parsed.get("ru_title") or "критические уязвимости").strip()
    for junk in ("Дайджест угроз:", "Дайджест угроз", "Дайджест:", "Дайджест", "Digest:", "Digest"):
        if subject.startswith(junk):
            subject = subject[len(junk):].lstrip(": -—").strip()
            break
    ru_title = f"Дайджест угроз {RU_MONTHS[today.month - 1]} {today.day} {today.year}: {subject}"
    ru_summary = parsed.get("ru_summary") or ""
    ru_explainer = parsed.get("ru_explainer") or ""
    tags = parsed.get("tags") or ["cve", "digest"]
    referenced_cve_ids = parsed.get("referenced_cve_ids") or all_cve_ids

    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                text("""
                    INSERT INTO kb_entries
                        (source, source_id, cve_id, raw_en_text, ru_title, ru_summary,
                         ru_explainer, tags, referenced_cve_ids, visible_in_kb_list)
                    VALUES
                        ('digest', :source_id, NULL, :raw_en_text, :ru_title, :ru_summary,
                         :ru_explainer, :tags, :referenced_cve_ids, true)
                    RETURNING id
                """),
                {
                    "source_id": f"digest-{date.today().isoformat()}",
                    "raw_en_text": input_text,
                    "ru_title": ru_title,
                    "ru_summary": ru_summary,
                    "ru_explainer": ru_explainer,
                    "tags": tags,
                    "referenced_cve_ids": referenced_cve_ids,
                },
            )
            entry_id = result.scalar_one()
            await session.commit()
            logger.info("daily_pipeline: digest created id=%s (covers %d CVEs)", entry_id, len(all_cve_ids))
            return entry_id
        except Exception as exc:
            await session.rollback()
            logger.error("daily_pipeline: failed to save digest: %s", exc)
            return None


async def _grpo_generate_task_for_kb_entry(
    entry: dict,
    *,
    task_type: str | None = None,
    difficulty: str | None = None,
) -> int | None:
    """Run GRPO pipeline for one CVE, publish best-passing variant as draft Task.
    Returns task.id or None.
    task_type and difficulty override inference when provided."""
    if task_type is None:
        cwe_ids = list(entry.get("cwe_ids") or [])
        attack_vector = entry.get("attack_vector")
        task_type = infer_task_type(cwe_ids, attack_vector)
    if difficulty is None:
        difficulty = _cvss_to_grpo_difficulty(entry.get("cvss_base_score"))
    num_variants = settings.AI_GEN_NUM_VARIANTS
    cve_id = entry.get("cve_id")
    batch_id = uuid.uuid4()

    # Create batch row (own session — pipeline opens its own sessions internally)
    async with AsyncSessionLocal() as session:
        batch = AIGenerationBatch(
            id=batch_id,
            requested_by=None,
            task_type=task_type,
            difficulty=difficulty,
            num_variants=num_variants,
            status="pending",
        )
        session.add(batch)
        await session.commit()

    # Run GRPO pipeline (long-running; opens its own DB sessions inside)
    async with AsyncSessionLocal() as pipeline_session:
        try:
            await run_pipeline(
                task_type=task_type,
                difficulty=difficulty,
                num_variants=num_variants,
                user_id=None,
                batch_id=batch_id,
                db=pipeline_session,
                cve_id=cve_id,
                topic=None,
            )
        except Exception as exc:
            logger.error("daily_pipeline: GRPO pipeline failed for cve=%s: %s", cve_id, exc)
            return None

    # Pick best passing variant
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AIGenerationVariant)
            .where(
                AIGenerationVariant.batch_id == batch_id,
                AIGenerationVariant.passed_all_binary == True,  # noqa: E712
            )
            .order_by(AIGenerationVariant.advantage.desc().nullslast())
            .limit(1)
        )
        variant = result.scalar_one_or_none()
        if not variant:
            logger.info("daily_pipeline: no passing variant for cve=%s", cve_id)
            return None

        batch_row = (
            await session.execute(select(AIGenerationBatch).where(AIGenerationBatch.id == batch_id))
        ).scalar_one_or_none()
        if not batch_row:
            return None

        spec = variant.generated_spec or {}
        artifact = variant.artifact_result or {}
        ciphertext = artifact.get("content")
        file_url = artifact.get("file_url")
        verification_data = artifact.get("verification_data") or {}

        access_type = ACCESS_TYPE_MAP.get(batch_row.task_type, "just_flag")
        is_chat = access_type == "chat"

        base_desc = spec.get("description") or spec.get("participant_description") or ""
        if not is_chat and ciphertext and ciphertext not in base_desc:
            participant_desc = (
                f"{base_desc}\n\nCiphertext (what you need to decode):\n```\n{ciphertext}\n```"
                if base_desc
                else f"Ciphertext (what you need to decode):\n```\n{ciphertext}\n```"
            )
        else:
            participant_desc = base_desc

        title = spec.get("title") or f"AI Generated — {batch_row.task_type}"
        # Avoid duplicate-title conflicts (Task.title is not unique in schema but
        # admin route enforces uniqueness; we silently skip duplicates here).
        dup = await session.execute(select(Task.id).where(Task.title == title))
        if dup.scalar_one_or_none():
            logger.warning("daily_pipeline: duplicate task title, skipping cve=%s title=%r", cve_id, title)
            return None

        chat_extras: dict = {}
        if is_chat:
            chat_extras["chat_system_prompt_template"] = ciphertext or ""
            for field in ("chat_user_message_max_chars", "chat_model_max_output_tokens", "chat_session_ttl_minutes"):
                raw = spec.get(field)
                if raw is not None:
                    try:
                        chat_extras[field] = int(raw)
                    except (TypeError, ValueError):
                        pass

        task = Task(
            title=title,
            category=batch_row.task_type.split("_")[0].capitalize(),
            task_kind="practice",
            difficulty=DIFFICULTY_INT_MAP.get(batch_row.difficulty, 2),
            points=DIFFICULTY_POINTS_MAP.get(batch_row.difficulty, 100),
            access_type=access_type,
            story=spec.get("story") or spec.get("description"),
            participant_description=participant_desc,
            kb_entry_id=entry["id"],
            llm_raw_response=spec,
            created_by=None,
            state="draft",
            **chat_extras,
        )
        session.add(task)
        await session.flush()

        flag_value = spec.get("flag", "")
        if flag_value and not is_chat:
            session.add(TaskFlag(
                task_id=task.id,
                flag_id="main",
                format="static",
                expected_value=flag_value,
                description="Auto-generated flag",
            ))

        if ciphertext or file_url:
            crypto_chain = verification_data.get("chain") or spec.get("crypto_chain")
            mat_kwargs: dict = dict(
                task_id=task.id,
                type="artifact",
                name="Generated artifact",
                description=f"Auto-generated artifact for {batch_row.task_type}",
                url=file_url,
                meta={"content": ciphertext, "crypto_chain": crypto_chain, "task_type": batch_row.task_type},
            )
            if file_url and batch_row.task_type == "forensics_image_metadata":
                mat_kwargs["name"] = "Forensics image"
                mat_kwargs["storage_key"] = file_url
            session.add(TaskMaterial(**mat_kwargs))

        crypto_chain = verification_data.get("chain") or spec.get("crypto_chain")
        if crypto_chain:
            forward_steps = [
                {"step": i + 1, "cipher": op.get("cipher"), "params": op.get("params", {}), "direction": "encrypt"}
                for i, op in enumerate(crypto_chain)
            ]
            reversed_steps = [
                {"step": i + 1, "cipher": op.get("cipher"), "params": op.get("params", {}), "direction": "reverse"}
                for i, op in enumerate(reversed(crypto_chain))
            ]
            chain_summary = " → ".join(op.get("cipher", "?") for op in crypto_chain)
            session.add(TaskAuthorSolution(
                task_id=task.id,
                summary=f"Reverse the encryption chain: {chain_summary}",
                creation_solution=f"Flag was encrypted with: {chain_summary}",
                steps={"encrypt": forward_steps, "decrypt": reversed_steps},
            ))

        variant.is_selected = True
        variant.published_task_id = task.id
        batch_row.selected_variant_id = variant.id

        try:
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error("daily_pipeline: failed to publish task for cve=%s: %s", cve_id, exc)
            return None

        logger.info("daily_pipeline: published task id=%s cve=%s task_type=%s", task.id, cve_id, batch_row.task_type)
        return task.id


async def _generate_tasks_for_top(today_entries: list, limit: int) -> list[int]:
    if not today_entries:
        return []

    slots = _TASK_SLOTS[:limit]
    top = today_entries[:len(slots)]
    semaphore = asyncio.Semaphore(settings.DAILY_PIPELINE_CONCURRENCY)

    async def _bounded(entry, task_type, difficulty):
        async with semaphore:
            return await _grpo_generate_task_for_kb_entry(entry, task_type=task_type, difficulty=difficulty)

    results = await asyncio.gather(
        *[_bounded(e, t, d) for e, (t, d) in zip(top, slots)],
        return_exceptions=True,
    )
    task_ids = [r for r in results if isinstance(r, int)]
    logger.info("daily_pipeline: created %d/%d draft tasks via GRPO", len(task_ids), len(top))
    return task_ids


async def run_daily_pipeline(*, force: bool = False) -> dict:
    if not force and await _is_recently_completed():
        logger.info("daily_pipeline: already completed in last 20h, skipping")
        return {"status": "already_done"}

    pipeline_start = datetime.now(timezone.utc)
    logger.info("daily_pipeline: starting NVD sync at %s", pipeline_start.isoformat())
    try:
        sync_result = await run_sync(
            hours=24,
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

    hidden_count = await _hide_all_nvd_entries()
    logger.info("daily_pipeline: hid %d NVD entries from public KB list", hidden_count)

    if not settings.DAILY_DIGEST_ENABLED:
        return {
            "status": "done",
            "sync": {k: v for k, v in sync_result.items() if k != "inserted_rows"},
            "hidden": hidden_count,
            "digest_id": None,
            "task_count": 0,
        }

    today_entries = await _select_today_entries()
    logger.info("daily_pipeline: %d translated entries created today", len(today_entries))

    digest_id = await _generate_digest(today_entries)
    task_ids = await _generate_tasks_for_top(today_entries, limit=settings.DAILY_TASK_COUNT)

    return {
        "status": "done",
        "sync": {k: v for k, v in sync_result.items() if k != "inserted_rows"},
        "hidden": hidden_count,
        "today_count": len(today_entries),
        "digest_id": digest_id,
        "task_count": len(task_ids),
    }
