import queue
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
from typing import Optional

from playwright.sync_api import sync_playwright, Browser, BrowserContext
from playwright_stealth import Stealth

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.exceptions import ScrapeBotDetectedError, ScrapeError, ScrapeTimeoutError
from app.scrapers.amazon import AmazonScraper
from app.scrapers.flipkart import FlipkartScraper
from app.scrapers.scraperapi_fallback import ScraperAPIFallback
from app.repositories.product_repo import ProductRepository
from app.repositories.price_history_repo import PriceHistoryRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


@dataclass
class ScrapeJob:
    """
    One unit of work dequeued from scrape_queue by a ScraperWorker.
    Published by RunManager at the start of each scraper cycle.
    """
    product_id: uuid.UUID
    url: str
    platform: str
    run_id: uuid.UUID


@dataclass
class NotificationJob:
    """
    Published to email_queue by ScraperWorker when a price drop is detected.
    Consumed by EmailWorker.
    """
    product_id: uuid.UUID
    product_name: Optional[str]
    product_image_url: Optional[str]
    product_url: str
    old_price: Decimal
    new_price: Decimal
    run_id: uuid.UUID


class ScraperWorker:
    """
    Long-running worker thread that processes ScrapeJobs from scrape_queue.

    Each worker owns exactly one Playwright Browser instance for its lifetime.
    A fresh BrowserContext is created per job and closed after extraction,
    ensuring full cookie/storage isolation between products.

    On price drop: publishes a NotificationJob to email_queue.
    On failure: logs and records scrape_status in price_history, moves on.

    The worker loop runs until it dequeues a sentinel None value (shutdown
    signal from WorkerManager).
    """

    def __init__(
        self,
        worker_id: int,
        scrape_queue: queue.Queue,
        email_queue: queue.Queue,
    ) -> None:
        self.worker_id = worker_id
        self.scrape_queue = scrape_queue
        self.email_queue = email_queue
        self._amazon = AmazonScraper()
        self._flipkart = FlipkartScraper()
        self._fallback = ScraperAPIFallback()
        self._browser: Optional[Browser] = None

    def run(self) -> None:
        """
        Main worker loop. Launched as a daemon thread by WorkerManager.

        Initialises Playwright and a Chromium browser, then loops on the
        scrape_queue until a None sentinel is received.
        Playwright and browser are cleaned up in a finally block.
        """
        logger.info(f"Worker starting, worker_id={self.worker_id}")
        with sync_playwright() as pw:
            self._browser = pw.chromium.launch(headless=True)
            try:
                self._loop()
            finally:
                self._browser.close()
                logger.info(f"Worker stopped - worker_id={self.worker_id}")
    def _loop(self) -> None:
        """
        Inner loop: dequeue jobs and process them until sentinel received.
        A None value in the queue signals graceful shutdown.
        """
        while True:
            job = self.scrape_queue.get()
            if job is None:
                logger.info(
                    f"Worker received shutdown sentinel - worker_id={self.worker_id}")
                self.scrape_queue.task_done()
                break
            try:
                self._process_job(job)
            except Exception as exc:
                logger.error(
                    f"Unhandled exception in worker job -"
                    f"worker_id={self.worker_id}, "
                    f"product_id={str(job.product_id)} , "
                    f"error={str(exc)}"
                )
            finally:
                self.scrape_queue.task_done()

    def _process_job(self, job: ScrapeJob) -> None:
        """
        Process one ScrapeJob with retry logic and ScraperAPI fallback.

        Retry strategy:
          - Up to settings.scrape_retry_limit attempts
          - Exponential backoff: 2s, 4s, 8s
          - On bot detection: route to ScraperAPI fallback immediately
          - On fallback failure: mark as failed, move on
        """
        scraper = (
            self._amazon if job.platform == "amazon" else self._flipkart
        )
        last_error: Optional[Exception] = None
        result = None

        for attempt in range(1, settings.scrape_retry_limit + 1):
            context: Optional[BrowserContext] = None
            try:
                context = self._browser.new_context(
                    viewport={"width": 1280, "height": 800},
                    locale="en-IN",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                )
                page = context.new_page()
                Stealth().apply_stealth_sync(page)
                result = scraper.extract(page, job.url)
                break  # success — exit retry loop

            except ScrapeBotDetectedError as exc:
                logger.warning(
                    f"Bot detected — routing to ScraperAPI,"
                    f"worker_id={self.worker_id},"
                    f"product_id={str(job.product_id)},"
                    f"attempt={attempt}"
                )
                last_error = exc
                try:
                    result = self._fallback.scrape(job.url, job.platform)
                    break
                except ScrapeError as fallback_exc:
                    last_error = fallback_exc
                    break  # fallback failed — do not retry further

            except (ScrapeError, ScrapeTimeoutError) as exc:
                last_error = exc
                if attempt < settings.scrape_retry_limit:
                    backoff = 2 ** attempt
                    logger.warning(
                        f"Scrape failed, retrying,"
                        f"worker_id={self.worker_id}, "
                        f"product_id={str(job.product_id)}, "
                        f"attempt={attempt},"
                        f"backoff_seconds={backoff},"
                        f"error={str(exc)}"
                    )
                    time.sleep(backoff)

            finally:
                if context:
                    context.close()

        self._write_result(job, result, last_error)

    def _write_result(
        self,
        job: ScrapeJob,
        result,
        last_error: Optional[Exception],
    ) -> None:
        """
        Persist the scrape outcome to the database and enqueue notifications.

        Opens its own DB session — workers are long-lived threads that run
        outside the FastAPI request lifecycle.
        """
        db = SessionLocal()
        try:
            product_repo = ProductRepository(db)
            ph_repo = PriceHistoryRepository(db)

            product = product_repo.get_by_id(job.product_id)
            if product is None:
                logger.error(
                    f"Product not found in DB during scrape write,"
                    f"product_id={str(job.product_id)}"
                )
                return

            # ── Scrape failed ─────────────────────────────────────────────
            if result is None:
                scrape_status = (
                    "blocked"
                    if isinstance(last_error, ScrapeBotDetectedError)
                    else "failed"
                )
                ph_repo.insert(
                    product_id=job.product_id,
                    price=None,
                    scrape_status=scrape_status,
                    run_id=job.run_id,
                )
                logger.error(
                    f"Scrape permanently failed,"
                    f"product_id={str(job.product_id)},"
                    f"scrape_status={scrape_status},"
                    "error={str(last_error)}"
                )
                db.commit()
                return

            # ── Scrape succeeded — detect price drop ──────────────────────
            old_price = product.current_price
            new_price = result.current_price
            price_dropped = (
                old_price is not None and new_price < old_price
            )

            if price_dropped:
                product_repo.update_current_price(product, new_price)
                logger.info(
                    f"Price drop detected ,"
                    f"product_id={str(job.product_id)},"
                    f"old_price={str(old_price)},"
                    f"new_price={str(new_price)}"
                )
                self.email_queue.put(NotificationJob(
                    product_id=job.product_id,
                    product_name=product.name,
                    product_image_url=product.image_url,
                    product_url=product.url,
                    old_price=old_price,
                    new_price=new_price,
                    run_id=job.run_id,
                ))

            # Always refresh metadata from the latest scrape
            product_repo.update_from_live_data(
                product,
                {
                    "name": result.name,
                    "brand": result.brand,
                    "image_url": result.image_url,
                    "availability": result.availability,
                    "rating": result.rating,
                    "review_count": result.review_count,
                    "seller": result.seller,
                    "last_checked_at": datetime.now(timezone.utc),
                },
            )

            ph_repo.insert(
                product_id=job.product_id,
                price=new_price,
                scrape_status="success",
                run_id=job.run_id,
            )

            db.commit()
            logger.info(
                f"Scrape succeeded,"
                f"worker_id={self.worker_id},"
                f"product_id={str(job.product_id)},"
                f"price={str(new_price)},"
                f"price_dropped={price_dropped}"
            )

        except Exception as exc:
            db.rollback()
            logger.error(
                f"DB write failed after scrape,"
                f"product_id={str(job.product_id)},"
                f"error={str(exc)}"
            )
        finally:
            db.close()