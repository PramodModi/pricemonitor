import queue
from datetime import datetime, timezone

from sqlalchemy import select, func

from app.core.database import SessionLocal
from app.core.models import PriceHistory, NotificationLog
from app.repositories.product_repo import ProductRepository
from app.repositories.scheduler_run_repo import SchedulerRunRepository
from app.workers.scraper_worker import ScrapeJob
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RunManager:
    """
    Orchestrates a single price-check cycle.

    Executed by:
    - GitHub Actions (primary trigger): scraper_entrypoint.py calls run()
    - APScheduler fallback (in FastAPI process): calls run() via scheduled job

    Responsibilities:
    1. Create a SchedulerRun row (status='running')
    2. Fetch all products from the database
    3. Enqueue one ScrapeJob per product onto scrape_queue
    4. Wait for the queue to drain (all jobs processed)
    5. Update the SchedulerRun row with final status and metrics
    """

    def __init__(self, scrape_queue: queue.Queue) -> None:
        self.scrape_queue = scrape_queue

    def run(self) -> None:
        """
        Execute one full price-check cycle.

        Creates a scheduler_run record, enqueues all products, waits for
        completion, and records final metrics. Handles database failures
        gracefully — a DB error marks the run as 'failed' before exiting.
        """
        db = SessionLocal()
        run = None

        try:
            run_repo = SchedulerRunRepository(db)
            product_repo = ProductRepository(db)

            # Step 1 — create run record
            run = run_repo.create()
            db.commit()
            logger.info(f"Scheduler run started — run_id={run.run_id}")

            # Step 2 — fetch all products
            products = product_repo.get_all_for_scraping()
            total = len(products)
            logger.info(f"Products fetched for scraping — count={total}")

            if total == 0:
                run_repo.complete(
                    run,
                    status="completed",
                    products_total=0,
                    products_scraped=0,
                    products_failed=0,
                    price_drops_found=0,
                    emails_sent=0,
                )
                db.commit()
                logger.info("No products to scrape — run marked completed")
                return

            # Step 3 — enqueue one job per product
            for product in products:
                self.scrape_queue.put(ScrapeJob(
                    product_id=product.product_id,
                    url=product.url,
                    platform=product.platform,
                    run_id=run.run_id,
                ))
            logger.info(f"Enqueued {total} scrape jobs")

            # Step 4 — wait for all workers to finish
            self.scrape_queue.join()
            logger.info("All scrape jobs completed")

            # Step 5 — collect metrics and finalise run
            metrics = self._collect_metrics(db, run.run_id, total)
            final_status = "partial" if metrics["products_failed"] > 0 else "completed"

            run_repo.complete(run, status=final_status, **metrics)
            db.commit()
            logger.info(
                f"Scheduler run finished — "
                f"run_id={run.run_id}, "
                f"status={final_status}, "
                f"scraped={metrics['products_scraped']}, "
                f"failed={metrics['products_failed']}, "
                f"drops={metrics['price_drops_found']}, "
                f"emails={metrics['emails_sent']}"
            )

        except Exception as exc:
            logger.error(f"Scheduler run failed — error={str(exc)}")
            db.rollback()
            if run:
                try:
                    run_repo = SchedulerRunRepository(db)
                    run_repo.mark_failed(run)
                    db.commit()
                except Exception as inner:
                    logger.error(f"Failed to mark run as failed — error={str(inner)}")
        finally:
            db.close()

    def _collect_metrics(self, db, run_id, total: int) -> dict:
        """
        Query price_history and notification_log to compute run metrics.

        Args:
            db: Active SQLAlchemy session.
            run_id: The SchedulerRun UUID.
            total: Total products enqueued.

        Returns:
            Dict with keys: products_total, products_scraped, products_failed,
            price_drops_found, emails_sent.
        """
        scraped = db.scalar(
            select(func.count(PriceHistory.history_id)).where(
                PriceHistory.run_id == run_id,
                PriceHistory.scrape_status == "success",
            )
        ) or 0

        failed = db.scalar(
            select(func.count(PriceHistory.history_id)).where(
                PriceHistory.run_id == run_id,
                PriceHistory.scrape_status.in_(["failed", "blocked"]),
            )
        ) or 0

        emails_sent = db.scalar(
            select(func.count(NotificationLog.notification_id)).where(
                NotificationLog.run_id == run_id,
                NotificationLog.status == "sent",
            )
        ) or 0

        drops = db.scalar(
            select(func.count(func.distinct(NotificationLog.product_id))).where(
                NotificationLog.run_id == run_id,
                NotificationLog.status == "sent",
            )
        ) or 0

        return {
            "products_total": total,
            "products_scraped": scraped,
            "products_failed": failed,
            "price_drops_found": drops,
            "emails_sent": emails_sent,
        }