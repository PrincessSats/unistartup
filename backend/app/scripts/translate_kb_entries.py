"""
Backfill script: Translate existing kb_entries that don't have ru_title/ru_summary/ru_explainer.

Run from backend directory:
    cd backend
    python -m app.scripts.translate_kb_entries

Or directly:
    cd backend
    python app/scripts/translate_kb_entries.py

Examples:
    # Count entries needing translation (dry run)
    python -m app.scripts.translate_kb_entries --dry-run

    # Test with 5 entries
    python -m app.scripts.translate_kb_entries --limit 5

    # Translate all entries with 0.5s delay between entries
    python -m app.scripts.translate_kb_entries

    # Translate all entries without delay (faster, but may hit rate limits)
    python -m app.scripts.translate_kb_entries --delay 0

Cost estimate (deepseek-v32 @ 0.5 RUB/1K tokens input + 0.5 RUB/1K tokens output):
- ~100 tokens in (title) + ~50 tokens out = 150 tokens for title
- ~600 tokens in (summary 3000 chars) + ~300 tokens out = 900 tokens for summary
- ~2000 tokens in (explainer 8000 chars) + ~1000 tokens out = 3000 tokens for explainer
- Total per CVE: ~4050 tokens × 0.5 RUB/1000 = ~2 RUB per CVE
- 1000 entries: ~2000 RUB
- 3863 entries: ~7700 RUB (one-time cost for full Russian KB)

Progress is displayed as a progress bar and logged to nvd_sync_log table for admin monitoring.
"""

import argparse
import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from tqdm import tqdm

from app.database import AsyncSessionLocal
from app.services.ai_generator.translation_service import TranslationService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress verbose HTTP client logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

BATCH_SIZE = 20  # translate 20 entries per batch to avoid rate limits
DELAY_SECONDS = 0.5  # pause between batches


async def create_translation_log(session: AsyncSession) -> int:
    """Create a log entry for this translation run."""
    result = await session.execute(
        text(
            """
            INSERT INTO nvd_sync_log (
                fetched_at,
                fetched_count,
                inserted_count,
                embedding_total,
                embedding_completed,
                embedding_failed,
                translation_total,
                translation_completed,
                translation_failed,
                status,
                error
            )
            VALUES (
                now(), 0, 0, 0, 0, 0, 0, 0, 0, 'translating', NULL
            )
            RETURNING id
            """
        )
    )
    row = result.fetchone()
    await session.commit()
    return row[0] if row else 0


async def update_translation_progress(
    session: AsyncSession,
    log_id: int,
    completed: int,
    failed: int,
) -> None:
    """Update translation progress in the log."""
    await session.execute(
        text(
            """
            UPDATE nvd_sync_log
            SET translation_completed = :completed,
                translation_failed = :failed
            WHERE id = :log_id
            """
        ),
        {"log_id": log_id, "completed": completed, "failed": failed},
    )
    await session.commit()


async def mark_translation_complete(session: AsyncSession, log_id: int, error: Optional[str]) -> None:
    """Mark translation run as complete or failed."""
    status = "failed" if error else "success"
    await session.execute(
        text(
            """
            UPDATE nvd_sync_log
            SET status = :status,
                error = :error
            WHERE id = :log_id
            """
        ),
        {"log_id": log_id, "status": status, "error": error[:500] if error else None},
    )
    await session.commit()


async def translate_existing_entries(
    *,
    dry_run: bool = False,
    limit: Optional[int] = None,
    delay_seconds: float = 0.5,
) -> None:
    """
    Translate all kb_entries WHERE ru_title IS NULL OR ru_summary IS NULL OR ru_explainer IS NULL.

    Translates FULL content: ru_title + ru_summary + ru_explainer using deepseek-v32.

    Args:
        dry_run: If True, only count entries without translating
        limit: Maximum number of entries to translate (for testing)
        delay_seconds: Pause between entries (seconds), set to 0 to disable
    """
    async with AsyncSessionLocal() as session:
        # Count entries needing translation
        result = await session.execute(
            text(
                """
                SELECT COUNT(*)
                FROM kb_entries
                WHERE raw_en_text IS NOT NULL
                  AND LENGTH(TRIM(raw_en_text)) > 0
                  AND (
                    ru_title IS NULL OR 
                    ru_summary IS NULL OR 
                    ru_explainer IS NULL
                  )
                """
            )
        )
        total_count = result.scalar() or 0
        logger.info("Found %d entries needing full translation", total_count)

        if total_count == 0:
            logger.info("All entries already have full Russian translation")
            return

        if dry_run:
            logger.info("DRY RUN: Would translate %d entries (full: title+summary+explainer)", total_count)
            return

        # Create log entry
        log_id = await create_translation_log(session)
        logger.info("Created translation log entry: id=%d", log_id)

    translation_svc = TranslationService()
    translated = 0
    failed = 0

    try:
        async with AsyncSessionLocal() as session:
            # Fetch entries needing translation
            query = text(
                """
                SELECT id, cve_id, raw_en_text
                FROM kb_entries
                WHERE raw_en_text IS NOT NULL
                  AND LENGTH(TRIM(raw_en_text)) > 0
                  AND (
                    ru_title IS NULL OR
                    ru_summary IS NULL OR
                    ru_explainer IS NULL
                  )
                ORDER BY created_at DESC
                """ + (f"LIMIT {limit}" if limit else "")
            )
            result = await session.execute(query)
            entries = result.fetchall()

        total_entries = len(entries)
        logger.info("Translating %d entries (FULL: title + summary + explainer)...", total_entries)

        # Create async helper for single entry translation
        async def translate_single_entry(entry):
            """Translate a single entry and update progress."""
            nonlocal translated, failed
            entry_id, cve_id, raw_en_text = entry

            try:
                result = await translation_svc.translate_full_cve(
                    cve_id or f"entry_{entry_id}",
                    raw_en_text or "",
                )

                if result.ru_title or result.ru_summary or result.ru_explainer:
                    async with AsyncSessionLocal() as session:
                        await session.execute(
                            text(
                                """
                                UPDATE kb_entries
                                SET ru_title = :ru_title,
                                    ru_summary = :ru_summary,
                                    ru_explainer = :ru_explainer
                                WHERE id = :entry_id
                                """
                            ),
                            {
                                "ru_title": result.ru_title or None,
                                "ru_summary": result.ru_summary or None,
                                "ru_explainer": result.ru_explainer or None,
                                "entry_id": entry_id,
                            },
                        )
                        await session.commit()
                    translated += 1
                else:
                    failed += 1
                    logger.warning("Translation returned empty for entry %d", entry_id)

            except Exception as exc:
                failed += 1
                logger.error("Translation failed for entry %d (%s): %s", entry_id, cve_id, exc)

            # Update progress in DB every 10 entries to reduce DB load
            if (translated + failed) % 10 == 0:
                async with AsyncSessionLocal() as session:
                    await update_translation_progress(session, log_id, translated, failed)

        # Process entries with progress bar
        with tqdm(
            total=total_entries,
            desc="Translating",
            unit="entry",
            bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}, {rate_fmt}]",
        ) as progress_bar:
            for entry in entries:
                await translate_single_entry(entry)
                progress_bar.update(1)
                # Delay between entries (for rate limiting)
                if delay_seconds > 0:
                    await asyncio.sleep(delay_seconds)

        # Final DB progress update
        async with AsyncSessionLocal() as session:
            await update_translation_progress(session, log_id, translated, failed)

        logger.info(
            "Translation complete: %d translated, %d failed out of %d total",
            translated, failed, total_entries,
        )

        await mark_translation_complete(session, log_id, None)

    except Exception as exc:
        logger.error("Translation backfill failed: %s", exc)
        async with AsyncSessionLocal() as session:
            await mark_translation_complete(session, log_id, str(exc))
        raise

    finally:
        await translation_svc.close()


def main():
    parser = argparse.ArgumentParser(description="Translate existing kb_entries to Russian")
    parser.add_argument("--dry-run", action="store_true", help="Count entries without translating")
    parser.add_argument("--limit", type=int, help="Limit number of entries to translate (for testing)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between entries (seconds), set to 0 to disable")
    args = parser.parse_args()

    logger.info("Starting translation backfill (dry_run=%s, limit=%s)", args.dry_run, args.limit)

    asyncio.run(translate_existing_entries(
        dry_run=args.dry_run,
        limit=args.limit,
        delay_seconds=args.delay,
    ))

    logger.info("Done!")


if __name__ == "__main__":
    main()
