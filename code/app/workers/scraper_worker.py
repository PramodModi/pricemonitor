"""
scraper_worker.py — long-running worker thread that processes ScrapeJobs.

Scraper selection is controlled by settings.use_scraper_v2 (default: True).

    use_scraper_v2 = True  → GenericScraper from app.scraper_v2 (production)
    use_scraper_v2 = False → AmazonScraper / FlipkartScraper from app.scrapers (fallback)

To roll back to the old scrapers without a code deploy, set USE_SCRAPER_V2=false
in Railway environment variables and redeploy.

Both paths share the same _write_result() and browser lifecycle — only
_process_job() branches on the flag.
"""

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
from app.repositories.product_repo import ProductRepository
from app.repositories.price_history_repo import PriceHistoryRepository
from app.utils.logging import get_logger

logger = get_logger(__name__)


# ── Job dataclasses (unchanged — consumed by RunManager and EmailWorker) ──────

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


# ── ScraperWorker ─────────────────────────────────────────────────────────────

class ScraperWorker:
    """
    Long-running worker thread that processes ScrapeJobs from scrape_queue.

    Each worker owns exactly one Playwright Browser instance for its lifetime.
    A fresh BrowserContext is created per job and closed after extraction,
    ensuring full cookie/storage isolation between products.

    Browser engine: Chromium by default. When use_scraper_v2=True and the
    portal config specifies browser="firefox" (e.g. Myntra), the worker
    launches Firefox instead. The old scraper path always uses Chromium.

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
        self._browser: Optional[Browser] = None

        # ── v1 scraper instances (only used when use_scraper_v2=False) ────────
        if not settings.use_scraper_v2:
            from app.scrapers.amazon import AmazonScraper
            from app.scrapers.flipkart import FlipkartScraper
            from app.scrapers.scraperapi_fallback import ScraperAPIFallback
            self._amazon = AmazonScraper()
            self._flipkart = FlipkartScraper()
            self._fallback = ScraperAPIFallback()

        # ── v2 scraper instance (shared across jobs — stateless between calls) ─
        if settings.use_scraper_v2:
            from app.scraper_v2.scrapers.generic_scraper import GenericScraper
            self._generic = GenericScraper()

        logger.info(
            f"ScraperWorker initialised — "
            f"worker_id={self.worker_id} "
            f"scraper={'v2' if settings.use_scraper_v2 else 'v1'}"
        )

    # ── Browser lifecycle ─────────────────────────────────────────────────────

    def run(self) -> None:
        """
        Main worker loop. Launched as a daemon thread by WorkerManager.

        Initialises Playwright and launches a browser, then loops on the
        scrape_queue until a None sentinel is received.
        Playwright and browser are cleaned up in a finally block.

        Browser engine: always Chromium in v1 mode. In v2 mode, Chromium
        is the default — Firefox is launched per-job when the portal config
        requires it (context is closed and reopened with Firefox for that job).
        The persistent browser here is Chromium; Firefox jobs open their own
        short-lived browser inline in _process_job_v2().
        """
        logger.info(f"Worker starting — worker_id={self.worker_id}")
        with sync_playwright() as pw:
            self._pw = pw
            self._browser = pw.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--disable-http2",
                ],
            )
            try:
                self._loop()
            finally:
                self._browser.close()
                logger.info(f"Worker stopped — worker_id={self.worker_id}")

    def _loop(self) -> None:
        """Inner loop: dequeue jobs until sentinel received."""
        while True:
            job = self.scrape_queue.get()
            if job is None:
                logger.info(f"Worker received shutdown sentinel — worker_id={self.worker_id}")
                self.scrape_queue.task_done()
                break
            try:
                self._process_job(job)
            except Exception as exc:
                logger.error(
                    f"Unhandled exception in worker job — "
                    f"worker_id={self.worker_id} "
                    f"product_id={str(job.product_id)} "
                    f"error={str(exc)}"
                )
            finally:
                self.scrape_queue.task_done()

    # ── Job dispatch ──────────────────────────────────────────────────────────

    def _process_job(self, job: ScrapeJob) -> None:
        """Route job to v2 or v1 scraper based on settings flag."""
        if settings.use_scraper_v2:
            self._process_job_v2(job)
        else:
            self._process_job_v1(job)

    # ── v2 path ───────────────────────────────────────────────────────────────

    def _process_job_v2(self, job: ScrapeJob) -> None:
        """
        Process one ScrapeJob using GenericScraper from scraper_v2.

        Key differences from v1:
        - Portal config drives browser engine — Firefox jobs open their own
          short-lived browser; Chromium jobs reuse self._browser.
        - GenericScraper.scrape() handles bot detection internally and returns
          a ScrapeResponse with success=False instead of raising.
        - Retry logic and exponential backoff are preserved.
        - ScrapeDiagnostic row written after every attempt (success or failure).
        """
        from app.scraper_v2.scrapers.registry import get_config
        from app.scraper_v2.core.exceptions import UnsupportedPlatformError
        from app.scraper_v2.models.scrape_result import ScrapeFailureReason

        try:
            portal_config = get_config(job.platform)
        except UnsupportedPlatformError:
            logger.error(
                f"Unsupported platform in scraper_v2 — "
                f"platform={job.platform} product_id={str(job.product_id)}"
            )
            self._write_result(job, result=None, last_error=None)
            return

        job_id = str(uuid.uuid4())
        last_response = None

        for attempt in range(1, settings.scrape_retry_limit + 1):
            browser_to_use = self._browser
            firefox_browser = None
            context: Optional[BrowserContext] = None

            try:
                # Firefox portals (e.g. Myntra) open their own short-lived browser
                if portal_config.browser == "firefox":
                    firefox_browser = self._pw.firefox.launch(headless=True)
                    browser_to_use = firefox_browser

                if job.platform == "myntra":
                    # Myntra: Firefox browser, no UA override.
                    # Firefox has a distinct TLS fingerprint that bypasses
                    # Myntra's bot detection. A Chrome UA on a Firefox TLS
                    # profile is a mismatch that gets flagged.
                    context = browser_to_use.new_context(
                        viewport={"width": 1280, "height": 800},
                        locale="en-IN",
                        extra_http_headers={
                            "Accept-Language": "en-IN,en;q=0.9",
                            "Accept": (
                                "text/html,application/xhtml+xml,application/xml;"
                                "q=0.9,image/avif,image/webp,*/*;q=0.8"
                            ),
                            "Accept-Encoding": "gzip, deflate, br",
                            "Upgrade-Insecure-Requests": "1",
                        },
                    )
                else:
                    # Amazon / Flipkart — original context, unchanged
                    context = browser_to_use.new_context(
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

                response = self._generic.scrape(
                    page=page,
                    url=job.url,
                    config=portal_config,
                    job_id=job_id,
                    attempt_number=attempt,
                    worker_id=self.worker_id,
                )

                # Write diagnostic row regardless of success/failure
                self._write_diagnostic(job, response)

                if response.success:
                    last_response = response
                    break  # success — exit retry loop

                # Failure — decide whether to retry
                error_type = response.error_type
                if error_type == ScrapeFailureReason.BOT_DETECTED:
                    logger.warning(
                        f"Bot detected — no retry for bot blocks — "
                        f"worker_id={self.worker_id} "
                        f"product_id={str(job.product_id)} "
                        f"attempt={attempt}"
                    )
                    last_response = response
                    break  # bot detection: don't retry (ScraperAPIFallback stub pending)

                if attempt < settings.scrape_retry_limit:
                    backoff = 2 ** attempt
                    logger.warning(
                        f"Scrape failed, retrying — "
                        f"worker_id={self.worker_id} "
                        f"product_id={str(job.product_id)} "
                        f"attempt={attempt} "
                        f"backoff_seconds={backoff} "
                        f"error_type={error_type}"
                    )
                    time.sleep(backoff)

                last_response = response

            except Exception as exc:
                logger.error(
                    f"Unexpected error in v2 scrape — "
                    f"worker_id={self.worker_id} "
                    f"product_id={str(job.product_id)} "
                    f"attempt={attempt} "
                    f"error={str(exc)}"
                )
            finally:
                if context:
                    context.close()
                if firefox_browser:
                    firefox_browser.close()

        # Convert ScrapeResponse → _write_result() compatible result
        if last_response and last_response.success:
            self._write_result(job, result=last_response, last_error=None)
        else:
            self._write_result(job, result=None, last_error=None)

    # ── v1 path (unchanged — preserved for rollback) ──────────────────────────

    def _process_job_v1(self, job: ScrapeJob) -> None:
        """
        Original scraper path using AmazonScraper / FlipkartScraper.
        Preserved intact for rollback. Activated when use_scraper_v2=False.
        """
        from app.core.exceptions import (
            ScrapeBotDetectedError,
            ScrapeError,
            ScrapeTimeoutError,
        )

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
                    timezone_id="Asia/Kolkata",
                    user_agent=(
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/124.0.0.0 Safari/537.36"
                    ),
                    extra_http_headers={
                        "Accept-Language": "en-IN,en;q=0.9",
                        "Accept": (
                            "text/html,application/xhtml+xml,application/xml;"
                            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
                        ),
                        "Accept-Encoding": "gzip, deflate, br",
                        "Upgrade-Insecure-Requests": "1",
                        "Sec-Fetch-Dest": "document",
                        "Sec-Fetch-Mode": "navigate",
                        "Sec-Fetch-Site": "none",
                        "Sec-Fetch-User": "?1",
                    },
                )
                page = context.new_page()
                Stealth().apply_stealth_sync(page)
                result = scraper.extract(page, job.url)
                break

            except ScrapeBotDetectedError as exc:
                logger.warning(
                    f"Bot detected — routing to ScraperAPI — "
                    f"worker_id={self.worker_id} "
                    f"product_id={str(job.product_id)} "
                    f"attempt={attempt}"
                )
                last_error = exc
                try:
                    result = self._fallback.scrape(job.url, job.platform)
                    break
                except ScrapeError as fallback_exc:
                    last_error = fallback_exc
                    break

            except (ScrapeError, ScrapeTimeoutError) as exc:
                last_error = exc
                if attempt < settings.scrape_retry_limit:
                    backoff = 2 ** attempt
                    logger.warning(
                        f"Scrape failed, retrying — "
                        f"worker_id={self.worker_id} "
                        f"product_id={str(job.product_id)} "
                        f"attempt={attempt} "
                        f"backoff_seconds={backoff} "
                        f"error={str(exc)}"
                    )
                    time.sleep(backoff)

            finally:
                if context:
                    context.close()

        self._write_result(job, result, last_error)

    # ── Shared write path ─────────────────────────────────────────────────────

    def _write_result(
        self,
        job: ScrapeJob,
        result,  # ScrapeResponse (v2) | ScrapeResult (v1) | None
        last_error: Optional[Exception],
    ) -> None:
        """
        Persist the scrape outcome to the database and enqueue notifications.

        Works with both ScrapeResponse (scraper_v2) and ScrapeResult (v1)
        because both expose the same field names used here:
            current_price, name, brand, image_url, availability,
            rating, review_count, seller.

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
                    f"Product not found in DB during scrape write — "
                    f"product_id={str(job.product_id)}"
                )
                return

            # ── Scrape failed ─────────────────────────────────────────────────
            if result is None:
                # Determine status: v1 uses exception type; v2 always passes
                # None here when all attempts failed (error_type logged earlier)
                from app.core.exceptions import ScrapeBotDetectedError as V1BotError
                scrape_status = (
                    "blocked"
                    if isinstance(last_error, V1BotError)
                    else "failed"
                )
                ph_repo.insert(
                    product_id=job.product_id,
                    price=None,
                    scrape_status=scrape_status,
                    run_id=job.run_id,
                )
                logger.error(
                    f"Scrape permanently failed — "
                    f"product_id={str(job.product_id)} "
                    f"scrape_status={scrape_status} "
                    f"error={str(last_error)}"
                )
                db.commit()
                return

            # ── Scrape succeeded — detect price change ─────────────────────────
            old_price = product.current_price
            new_price = result.current_price
            price_dropped = old_price is not None and new_price < old_price
            price_changed = old_price is not None and new_price != old_price

            if price_changed:
                product_repo.update_current_price(product, new_price)

            if price_dropped:
                logger.info(
                    f"Price drop detected — "
                    f"product_id={str(job.product_id)} "
                    f"old_price={str(old_price)} "
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
                f"Scrape succeeded — "
                f"worker_id={self.worker_id} "
                f"product_id={str(job.product_id)} "
                f"price={str(new_price)} "
                f"price_dropped={price_dropped}"
            )

        except Exception as exc:
            db.rollback()
            logger.error(
                f"DB write failed after scrape — "
                f"product_id={str(job.product_id)} "
                f"error={str(exc)}"
            )
        finally:
            db.close()

    # ── Diagnostic write (v2 only) ────────────────────────────────────────────

    def _write_diagnostic(self, job: ScrapeJob, response) -> None:
        """
        Write one row to scrape_diagnostics for observability.
        Called after every scrape attempt in v2 mode (success or failure).
        Silently swallows all errors — diagnostic writes must never abort a scrape.
        """
        try:
            from app.scraper_v2.diagnostics.repository import ScrapeDiagnosticRepository
            db = SessionLocal()
            try:
                repo = ScrapeDiagnosticRepository(db)
                repo.insert(
                    product_id=job.product_id,
                    run_id=job.run_id,
                    portal=response.portal,
                    worker_id=response.worker_id,
                    attempt_number=response.attempt_number,
                    success=response.success,
                    extraction_method=response.extraction_method,
                    error_type=(
                        response.error_type.value
                        if response.error_type else None
                    ),
                    error_message=response.error_message,
                    layers_attempted=(
                        ",".join(response.layers_attempted)
                        if response.layers_attempted else None
                    ),
                    layers_failed=(
                        ",".join(response.layers_failed)
                        if response.layers_failed else None
                    ),
                    navigation_ms=response.navigation_ms,
                    extraction_ms=response.extraction_ms,
                    total_duration_ms=response.total_duration_ms,
                )
                db.commit()
            finally:
                db.close()
        except Exception as exc:
            logger.warning(
                f"Failed to write scrape diagnostic — "
                f"product_id={str(job.product_id)} "
                f"error={str(exc)}"
            )
