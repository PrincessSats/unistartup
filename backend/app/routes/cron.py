import hmac
import logging

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.services.daily_pipeline import run_daily_pipeline

router = APIRouter(tags=["Cron"])
logger = logging.getLogger(__name__)


@router.post("/cron/daily/{secret}")
async def trigger_daily_pipeline(secret: str, force: bool = False):
    """Yandex Cloud Timer Trigger endpoint. Synchronous — blocks until pipeline done.
    Requires BACKEND_EXECUTION_TIMEOUT >= 1800s on the container revision."""
    cron_secret = (settings.CRON_SECRET or "").strip()
    if not cron_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CRON_SECRET not configured",
        )
    if not hmac.compare_digest(secret, cron_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    logger.info("daily_pipeline: starting (force=%s)", force)
    result = await run_daily_pipeline(force=force)
    logger.info("daily_pipeline: finished result=%s", result)
    return result
