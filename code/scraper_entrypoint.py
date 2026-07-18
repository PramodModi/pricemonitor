"""
scraper_entrypoint.py

GitHub Actions entry point for the scheduled scraper.

Invoked by the cron workflow every 4 hours:
    python scraper_entrypoint.py

Runs a single price-check cycle:
1. Starts a WorkerManager (3 Playwright workers)
2. Starts an EmailWorker
3. RunManager fetches all products and enqueues scrape jobs
4. Waits for all jobs to complete
5. Shuts down cleanly

Exit code 0 on success, 1 on failure (triggers GitHub Actions failure alert).
"""

import queue
import sys
import threading

from app.core.config import settings
from app.utils.logging import configure_logging, get_logger
from app.workers.worker_manager import WorkerManager
from app.workers.email_worker import EmailWorker
from app.scheduler.run_manager import RunManager


def main() -> int:
    configure_logging(settings.log_level)
    logger = get_logger(__name__)

    logger.info("PriceMonitor scraper starting")

    scrape_queue: queue.Queue = queue.Queue()
    email_queue: queue.Queue = queue.Queue()

    # Start worker pool
    worker_manager = WorkerManager(scrape_queue, email_queue)
    worker_manager.start()
    logger.info(f"WorkerManager started — workers={settings.max_scraper_workers}")

    # Start email worker
    email_worker = EmailWorker(email_queue)
    email_thread = threading.Thread(
        target=email_worker.run,
        daemon=True,
        name="EmailWorker",
    )
    email_thread.start()
    logger.info("EmailWorker started")

    try:
        # Run one full scrape cycle
        run_manager = RunManager(scrape_queue)
        run_manager.run()
        logger.info("Scrape cycle completed successfully")
        return 0

    except Exception as exc:
        logger.error(f"Scrape cycle failed — error={str(exc)}")
        return 1

    finally:
        # Graceful shutdown
        logger.info("Shutting down workers")
        worker_manager.shutdown()
        email_queue.put(None)
        email_thread.join(timeout=30)
        logger.info("PriceMonitor scraper finished")


if __name__ == "__main__":
    sys.exit(main())