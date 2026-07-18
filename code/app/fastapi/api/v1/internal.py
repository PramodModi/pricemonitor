from fastapi import APIRouter, Depends
from datetime import datetime, timezone

from app.fastapi.api.dependencies import verify_internal_token
from app.utils.logging import get_logger

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)
logger = get_logger(__name__)


@router.post("/trigger-run", status_code=202)
def trigger_run() -> dict:
    """
    Manually trigger a scrape run.
    The actual run is handled by the RunManager via the scrape_queue.
    Requires Bearer token.
    """
    from app.fastapi.main import scrape_queue
    from app.scheduler.run_manager import RunManager
    import threading

    run_manager = RunManager(scrape_queue)
    thread = threading.Thread(
        target=run_manager.run,
        daemon=True,
        name="ManualTriggerRun",
    )
    thread.start()
    logger.info("Manual scrape run triggered")

    return {
        "message": "Scrape run initiated.",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }