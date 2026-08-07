import queue
import time
from typing import Optional

from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.user_repo import UserRepository
from app.repositories.notification_log_repo import NotificationLogRepository
from app.notifications.email_sender import EmailSender
from app.workers.scraper_worker import NotificationJob
from app.utils.logging import get_logger

logger = get_logger(__name__)


class EmailWorker:
    """
    Single-threaded consumer of the email_queue.

    For each NotificationJob, fetches all subscriber emails for the product,
    sends one personalised price-drop email per subscriber via SendGrid,
    and records each delivery attempt in notification_log.

    Retry policy: up to settings.email_retry_limit attempts per recipient,
    with exponential backoff. SendGrid 4xx errors are not retried.
    """

    def __init__(self, email_queue: queue.Queue) -> None:
        self.email_queue = email_queue
        self._sender = EmailSender()

    def run(self) -> None:
        """
        Main loop. Runs as a daemon thread. Exits on None sentinel.
        """
        logger.info("EmailWorker started")
        while True:
            job = self.email_queue.get()
            if job is None:
                logger.info("EmailWorker received shutdown sentinel")
                self.email_queue.task_done()
                break
            try:
                self._process_notification(job)
            except Exception as exc:
                # FIX (DEV-006): was logger.error(..., product_id=..., error=...)
                # keyword args raise TypeError on standard logging.Logger,
                # which was itself swallowed — making every failure invisible.
                logger.error(
                    f"Unhandled exception in EmailWorker — "
                    f"product_id={str(job.product_id)} "
                    f"error={str(exc)}"
                )
            finally:
                self.email_queue.task_done()

    def _process_notification(self, job: NotificationJob) -> None:
        """
        Fan out one price-drop notification to all product subscribers.

        Fetches subscriber emails live from the database to ensure the list
        is current — users may have unsubscribed since the job was enqueued.
        """
        db = SessionLocal()
        try:
            sub_repo = SubscriptionRepository(db)
            user_repo = UserRepository(db)
            nl_repo = NotificationLogRepository(db)

            emails = sub_repo.get_subscriber_emails_for_product(job.product_id)
            # FIX (DEV-006): was logger.info(..., product_id=..., subscriber_count=...)
            logger.info(
                f"Dispatching price drop notifications — "
                f"product_id={str(job.product_id)} "
                f"subscriber_count={len(emails)}"
            )

            emails_sent = 0
            for email in emails:
                user = user_repo.get_by_email(email)
                if user is None:
                    continue

                status = self._deliver_with_retry(job, email)
                nl_repo.insert(
                    user_id=user.user_id,
                    product_id=job.product_id,
                    run_id=job.run_id,
                    old_price=job.old_price,
                    new_price=job.new_price,
                    status=status,
                )
                if status == "sent":
                    emails_sent += 1

            db.commit()
            # FIX (DEV-006): was logger.info(..., product_id=..., emails_sent=..., ...)
            logger.info(
                f"Notification fan-out complete — "
                f"product_id={str(job.product_id)} "
                f"emails_sent={emails_sent} "
                f"total_subscribers={len(emails)}"
            )

        except Exception as exc:
            db.rollback()
            # FIX (DEV-006): was logger.error(..., product_id=..., error=...)
            logger.error(
                f"DB error during notification fan-out — "
                f"product_id={str(job.product_id)} "
                f"error={str(exc)}"
            )
        finally:
            db.close()

    def _deliver_with_retry(self, job: NotificationJob, to_email: str) -> str:
        """
        Attempt to deliver one email with exponential backoff.
        Returns 'sent' on success, 'failed' after all retries exhausted.
        """
        for attempt in range(1, settings.email_retry_limit + 1):
            success = self._sender.send_price_drop(
                to_email=to_email,
                product_name=job.product_name or "Product",
                product_image_url=job.product_image_url,
                product_url=job.product_url,
                old_price=job.old_price,
                new_price=job.new_price,
                platform=self._infer_platform(job.product_url),
                mrp=job.mrp,
            )
            if success:
                return "sent"

            backoff = 2 ** attempt
            # FIX (DEV-006): was logger.warning(..., to_email=..., attempt=..., ...)
            logger.warning(
                f"Email delivery failed, retrying — "
                f"to_email={to_email} "
                f"attempt={attempt} "
                f"backoff_seconds={backoff}"
            )
            time.sleep(backoff)

        # FIX (DEV-006): was logger.error(..., to_email=..., product_id=...)
        logger.error(
            f"Email delivery permanently failed — "
            f"to_email={to_email} "
            f"product_id={str(job.product_id)}"
        )
        return "failed"

    @staticmethod
    def _infer_platform(url: str) -> str:
        # FIX: was binary amazon/flipkart — Myntra URLs were misidentified as flipkart
        if "amazon.in" in url:
            return "amazon"
        if "myntra.com" in url:
            return "myntra"
        return "flipkart"
