import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

from app.database import ensure_daily_pipeline_schema_compatibility
from app.services.daily_pipeline import run_daily_pipeline


async def main():
    await ensure_daily_pipeline_schema_compatibility()
    result = await run_daily_pipeline(force=True)
    print("RESULT:", result)


asyncio.run(main())
