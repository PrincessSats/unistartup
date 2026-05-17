import asyncio
import logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from app.database import ensure_daily_pipeline_schema_compatibility
from app.services.daily_pipeline import run_daily_pipeline

async def main():
    await ensure_daily_pipeline_schema_compatibility()
    from app.services.daily_pipeline import _select_top_cves, _generate_digest
    top = await _select_top_cves(limit=10)
    print(f"TOP CVEs found: {len(top)}")
    for r in top:
        print(f"  {r['cve_id']} cvss={r['cvss_base_score']} title={r['ru_title'][:40] if r['ru_title'] else None}")
    digest_id = await _generate_digest(top)
    print(f"DIGEST ID: {digest_id}")

asyncio.run(main())
