import asyncio
import hmac
import logging

from fastapi import APIRouter, HTTPException, status

from app.config import settings
from app.services.daily_pipeline import run_daily_pipeline

router = APIRouter(tags=["Cron"])
logger = logging.getLogger(__name__)

_cron_background_tasks: set[asyncio.Task] = set()


@router.post("/cron/daily/{secret}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_daily_pipeline(secret: str, force: bool = False):
    """Yandex Cloud Timer Trigger endpoint. Auth via path-embedded CRON_SECRET."""
    cron_secret = (settings.CRON_SECRET or "").strip()
    if not cron_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="CRON_SECRET not configured",
        )
    if not hmac.compare_digest(secret, cron_secret):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    task = asyncio.create_task(run_daily_pipeline(force=force))
    _cron_background_tasks.add(task)
    task.add_done_callback(_cron_background_tasks.discard)

    logger.info("daily_pipeline: background task queued (force=%s)", force)
    return {"status": "accepted"}
