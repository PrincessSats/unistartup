"""
Backlog article generation for kb_entries that have no Russian content yet.

Queries kb_entries WHERE source='nvd' AND ru_explainer IS NULL, then runs
_translate_entries_for_log (which now uses generate_article_payload) on them.

Usage:
    cd backend
    python -m scripts.backlog_generate_articles [--limit N] [--dry-run]
"""
import argparse
import asyncio
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.services.nvd_sync import _translate_entries_for_log

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


async def main() -> int:
    parser = argparse.ArgumentParser(description="Generate Russian KB articles for untranslated NVD entries")
    parser.add_argument("--limit", type=int, default=None, help="Max entries to process (default: all)")
    parser.add_argument("--dry-run", action="store_true", help="Show count only, do not generate")
    args = parser.parse_args()

    async with AsyncSessionLocal() as session:
        query = (
            "SELECT id, cve_id, raw_en_text, attack_vector "
            "FROM kb_entries "
            "WHERE source = 'nvd' AND (ru_explainer IS NULL OR ru_explainer = '') "
            "ORDER BY id"
        )
        if args.limit:
            query += f" LIMIT {args.limit}"

        result = await session.execute(text(query))
        rows = [dict(r) for r in result.mappings().all()]

    if not rows:
        logger.info("No untranslated entries found.")
        return 0

    logger.info("Found %d untranslated entries.", len(rows))

    if args.dry_run:
        logger.info("Dry run — exiting without generating.")
        return 0

    # Use log_id=0: the UPDATE on nvd_sync_log will match 0 rows (harmless).
    stats = await _translate_entries_for_log(0, rows)
    logger.info("Done. completed=%d, failed=%d", stats["completed"], stats["failed"])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
