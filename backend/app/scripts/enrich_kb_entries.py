"""
Backfill script: Enrich existing kb_entries with structured NVD metadata
(CWE IDs, CVSS scores, attack vectors, affected products).

Run from backend directory:
    cd backend
    python -m app.scripts.enrich_kb_entries

Examples:
    # Count entries needing enrichment (dry run)
    python -m app.scripts.enrich_kb_entries --dry-run

    # Test with 50 entries first
    python -m app.scripts.enrich_kb_entries --limit 50

    # Full backfill with NVD API key (faster: 0.6s delay)
    NVD_API_KEY=<key> python -m app.scripts.enrich_kb_entries

    # Re-embed entries after enrichment (updates pgvector embeddings)
    python -m app.scripts.enrich_kb_entries --re-embed

Cost: Zero LLM cost. NVD API is free.
Rate limits:
    - Without API key: 5 requests/30 seconds → ~38 min for 3863 entries
    - With API key:    50 requests/30 seconds → ~4 min for 3863 entries
"""

import argparse
import asyncio
import logging
import os
import time
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy import text
from tqdm import tqdm

from app.database import AsyncSessionLocal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

NVD_API_BASE = "https://services.nvd.nist.gov/rest/json/cves/2.0"
BATCH_SIZE = 10  # entries per DB commit batch


# ── NVD extraction helpers ─────────────────────────────────────────────────────

def _extract_cwe_ids(cve: dict) -> list[str]:
    cwe_ids: list[str] = []
    for weakness in cve.get("weaknesses", []):
        for desc in weakness.get("description", []):
            val = desc.get("value", "")
            if val.startswith("CWE-") and val not in ("CWE-noinfo", "CWE-Other"):
                cwe_ids.append(val)
    return list(dict.fromkeys(cwe_ids))  # deduplicate, preserve order


def _extract_cvss_data(cve: dict) -> dict:
    metrics = cve.get("metrics", {})
    for key in ("cvssMetricV31", "cvssMetricV30", "cvssMetricV2"):
        entries = metrics.get(key, [])
        if entries:
            data = entries[0].get("cvssData", {})
            return {
                "cvss_base_score": data.get("baseScore"),
                "cvss_vector": data.get("vectorString"),
                "attack_vector": data.get("attackVector") or data.get("accessVector"),
                "attack_complexity": data.get("attackComplexity") or data.get("accessComplexity"),
            }
    return {}


def _extract_affected_products(cve: dict) -> list[str]:
    products: list[str] = []
    for config in cve.get("configurations", []):
        for node in config.get("nodes", []):
            for match in node.get("cpeMatch", []):
                cpe = match.get("criteria", "")
                parts = cpe.split(":")
                if len(parts) >= 5:
                    vendor = parts[3]
                    product = parts[4]
                    entry = f"{vendor}:{product}"
                    if entry not in products:
                        products.append(entry)
                if len(products) >= 10:
                    return products
    return products


def _build_enriched_embedding_text(row: dict, cwe_ids: list[str], attack_vector: Optional[str]) -> str:
    """Rebuild embedding text with CWE and attack_vector included."""
    parts = []
    if row.get("cve_id"):
        parts.append(row["cve_id"])
    if cwe_ids:
        parts.append(" ".join(cwe_ids))
    if attack_vector:
        parts.append(f"attack_vector:{attack_vector}")
    if row.get("title"):
        parts.append(row["title"])
    if row.get("summary"):
        parts.append(row["summary"][:500])
    return " ".join(parts)


# ── NVD API fetch ──────────────────────────────────────────────────────────────

async def fetch_nvd_cve(cve_id: str, api_key: Optional[str], client: httpx.AsyncClient) -> Optional[dict]:
    """Fetch a single CVE from NVD API v2. Returns the cve dict or None on error."""
    headers = {}
    if api_key:
        headers["apiKey"] = api_key
    try:
        resp = await client.get(
            NVD_API_BASE,
            params={"cveId": cve_id},
            headers=headers,
            timeout=30.0,
        )
        resp.raise_for_status()
        data = resp.json()
        vulns = data.get("vulnerabilities", [])
        if not vulns:
            return None
        return vulns[0].get("cve")
    except Exception as exc:
        logger.warning("NVD fetch failed for %s: %s", cve_id, exc)
        return None


# ── DB operations ──────────────────────────────────────────────────────────────

async def count_pending(db) -> int:
    result = await db.execute(text("""
        SELECT COUNT(*) FROM kb_entries
        WHERE cve_id IS NOT NULL
          AND (cwe_ids IS NULL OR cwe_ids = '{}')
    """))
    return result.scalar()


async def fetch_pending_entries(db, limit: Optional[int]) -> list[dict]:
    limit_clause = f"LIMIT {limit}" if limit else ""
    result = await db.execute(text(f"""
        SELECT id, cve_id, title, summary, tags
        FROM kb_entries
        WHERE cve_id IS NOT NULL
          AND (cwe_ids IS NULL OR cwe_ids = '{{}}')
        ORDER BY id
        {limit_clause}
    """))
    rows = result.fetchall()
    return [dict(r._mapping) for r in rows]


async def update_entry(db, entry_id: int, cve_data: dict, re_embed: bool, embedding_svc=None) -> None:
    cwe_ids = cve_data.get("cwe_ids", [])
    cvss = cve_data.get("cvss_base_score")
    cvss_vector = cve_data.get("cvss_vector")
    attack_vector = cve_data.get("attack_vector")
    attack_complexity = cve_data.get("attack_complexity")
    affected_products = cve_data.get("affected_products", [])

    # Update tags to include CWE IDs
    tag_result = await db.execute(text("SELECT tags FROM kb_entries WHERE id = :id"), {"id": entry_id})
    row = tag_result.fetchone()
    existing_tags = list(row[0]) if row and row[0] else []
    new_tags = list(dict.fromkeys(existing_tags + [cw.lower() for cw in cwe_ids]))

    update_params: dict = {
        "id": entry_id,
        "cwe_ids": cwe_ids,
        "cvss_base_score": cvss,
        "cvss_vector": cvss_vector,
        "attack_vector": attack_vector,
        "attack_complexity": attack_complexity,
        "affected_products": affected_products,
        "tags": new_tags,
    }

    await db.execute(text("""
        UPDATE kb_entries SET
            cwe_ids = CAST(:cwe_ids AS text[]),
            cvss_base_score = :cvss_base_score,
            cvss_vector = :cvss_vector,
            attack_vector = :attack_vector,
            attack_complexity = :attack_complexity,
            affected_products = CAST(:affected_products AS text[]),
            tags = CAST(:tags AS text[])
        WHERE id = :id
    """), update_params)


# ── main ───────────────────────────────────────────────────────────────────────

async def run(args: argparse.Namespace) -> None:
    api_key = os.environ.get("NVD_API_KEY")
    delay = 6.0 if not api_key else 0.6

    async with AsyncSessionLocal() as db:
        pending = await count_pending(db)
        print(f"Entries needing enrichment: {pending}")

        if args.dry_run:
            return

        entries = await fetch_pending_entries(db, args.limit)
        print(f"Will process: {len(entries)} entries (delay={delay}s per request)")

        succeeded = 0
        failed = 0
        skipped = 0

        async with httpx.AsyncClient() as client:
            for i, entry in enumerate(tqdm(entries, desc="Enriching")):
                cve_id = entry["cve_id"]
                cve = await fetch_nvd_cve(cve_id, api_key, client)

                if cve is None:
                    skipped += 1
                    logger.debug("Skipped %s (no NVD data)", cve_id)
                else:
                    cwe_ids = _extract_cwe_ids(cve)
                    cvss_data = _extract_cvss_data(cve)
                    affected_products = _extract_affected_products(cve)

                    enriched = {
                        "cwe_ids": cwe_ids,
                        "affected_products": affected_products,
                        **cvss_data,
                    }

                    try:
                        await update_entry(db, entry["id"], enriched, args.re_embed)
                        succeeded += 1
                    except Exception as exc:
                        logger.error("DB update failed for %s: %s", cve_id, exc)
                        failed += 1

                # Commit every BATCH_SIZE entries
                if (i + 1) % BATCH_SIZE == 0:
                    await db.commit()
                    logger.info("Committed batch %d/%d", i + 1, len(entries))

                # Rate limiting
                if i < len(entries) - 1:
                    time.sleep(delay)

        # Final commit
        await db.commit()

    print(f"\nDone. succeeded={succeeded}, skipped={skipped}, failed={failed}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Enrich kb_entries with NVD structured metadata")
    parser.add_argument("--dry-run", action="store_true", help="Count pending entries and exit")
    parser.add_argument("--limit", type=int, default=None, help="Process at most N entries")
    parser.add_argument("--re-embed", action="store_true", help="Re-embed entries after enrichment (not yet implemented)")
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
