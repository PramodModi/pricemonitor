import queue
import threading
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI

from app.fastapi.api.v1 import products, subscriptions, items, runs, health, internal
from app.fastapi.api.error_handlers import register_error_handlers
from app.core.config import settings
from app.services.preview_cache import preview_cache
from app.workers.worker_manager import WorkerManager
from app.workers.email_worker import EmailWorker
from app.scheduler.run_manager import RunManager
from app.utils.logging import configure_logging, get_logger

logger = get_logger(__name__)

# Shared queues — module-level so internal.py can import them
scrape_queue: queue.Queue = queue.Queue()
email_queue: queue.Queue = queue.Queue()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup:
      - Configure logging
      - Start WorkerManager (scraper thread pool)
      - Start EmailWorker thread
      - Start APScheduler (price check every 4h + cache purge every 15min)

    Shutdown:
      - Graceful shutdown of all workers and scheduler
    """
    configure_logging(settings.log_level)
    logger.info("PriceWatch API starting up")

    # Worker pool
    worker_manager = WorkerManager(scrape_queue, email_queue)
    worker_manager.start()

    # Email worker
    email_worker = EmailWorker(email_queue)
    email_thread = threading.Thread(
        target=email_worker.run,
        daemon=True,
        name="EmailWorker",
    )
    email_thread.start()

    # APScheduler — fallback trigger + cache purge
    scheduler = BackgroundScheduler()
    run_manager = RunManager(scrape_queue)

    scheduler.add_job(
        run_manager.run,
        trigger="cron",
        hour="*/4",
        minute=0,
        id="price_check",
        max_instances=1,
        coalesce=True,
    )
    scheduler.add_job(
        preview_cache.purge_expired,
        trigger="interval",
        minutes=15,
        id="cache_purge",
    )
    scheduler.start()
    logger.info("APScheduler started")

    yield  # app is running

    # Shutdown
    logger.info("PriceWatch API shutting down")
    scheduler.shutdown(wait=False)
    worker_manager.shutdown()
    email_queue.put(None)
    email_thread.join(timeout=30)
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="PriceMonitor API",
        description="Price tracking for Amazon India and Flipkart.",
        version="1.0.0",
        lifespan=lifespan,
    )

    register_error_handlers(app)

    prefix = "/v1"
    app.include_router(health.router)
    app.include_router(products.router, prefix=prefix)
    app.include_router(subscriptions.router, prefix=prefix)
    app.include_router(items.router, prefix=prefix)
    app.include_router(runs.router, prefix=prefix)
    app.include_router(internal.router, prefix=prefix)

    return app


app = create_app()