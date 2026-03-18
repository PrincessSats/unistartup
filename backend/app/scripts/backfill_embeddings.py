"""
One-time backfill script: embed all kb_entries where embedding IS NULL.

Run:
    python -m app.scripts.backfill_embeddings

Processes entries in batches of 50 with a 0.5s delay between batches
to avoid rate-limiting the Yandex embedding API.
"""
from __future__ import annotations

import asyncio
import logging

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.contest import KBEntry
from app.services.ai_generator.embedding_service import EmbeddingService, EmbeddingError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

BATCH_SIZE = 50
BATCH_DELAY = 0.5  # seconds


async def backfill() -> None:
    svc = EmbeddingService()
    total_done = 0
    total_failed = 0

    try:
        async with AsyncSessionLocal() as db:
            # Count entries needing embeddings
            result = await db.execute(
                select(KBEntry).where(KBEntry.embedding.is_(None)).order_by(KBEntry.id)
            )
            entries = result.scalars().all()

        if not entries:
            logger.info("No kb_entries need embeddings — nothing to do.")
            return

        logger.info("Found %d kb_entries without embeddings.", len(entries))

        for batch_start in range(0, len(entries), BATCH_SIZE):
            batch = entries[batch_start : batch_start + BATCH_SIZE]
            logger.info(
                "Processing batch %d-%d / %d",
                batch_start + 1,
                batch_start + len(batch),
                len(entries),
            )

            async with AsyncSessionLocal() as db:
                for entry in batch:
                    text = " ".join(filter(None, [
                        entry.cve_id,
                        entry.ru_title,
                        entry.ru_summary,
                        entry.raw_en_text,
                    ]))
                    if not text.strip():
                        logger.warning("Skipping kb_entry id=%s — no text content", entry.id)
                        continue

                    try:
                        vector = await svc.embed_document(text)
                        # Re-fetch entry in this session
                        fresh = await db.get(KBEntry, entry.id)
                        if fresh is not None:
                            fresh.embedding = vector
                            total_done += 1
                    except EmbeddingError as exc:
                        logger.warning("Failed to embed kb_entry id=%s: %s", entry.id, exc)
                        total_failed += 1

                await db.commit()

            if batch_start + BATCH_SIZE < len(entries):
                await asyncio.sleep(BATCH_DELAY)

    finally:
        await svc.close()

    logger.info("Backfill complete: %d embedded, %d failed.", total_done, total_failed)


if __name__ == "__main__":
    asyncio.run(backfill())
