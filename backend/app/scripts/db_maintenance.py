import asyncio
import logging

from app.database import (
    ensure_auth_schema_compatibility,
    ensure_landing_hunt_schema_compatibility,
    ensure_performance_indexes,
)

logger = logging.getLogger(__name__)


async def run() -> None:
    await ensure_auth_schema_compatibility()
    await ensure_landing_hunt_schema_compatibility()
    await ensure_performance_indexes()
    logger.info("DB maintenance completed")


if __name__ == "__main__":
    asyncio.run(run())
