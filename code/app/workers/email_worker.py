import queue
import threading
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
                logger.error(
                    "Unhandled exception in EmailWorker",
                    product_id=str(job.product_id),
                    error=str(exc),
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
            logger.info(
                "Dispatching price drop notifications",
                product_id=str(job.product_id),
                subscriber_count=len(emails),
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
            logger.info(
                "Notification fan-out complete",
                product_id=str(job.product_id),
                emails_sent=emails_sent,
                total_subscribers=len(emails),
            )

        except Exception as exc:
            db.rollback()
            logger.error(
                "DB error during notification fan-out",
                product_id=str(job.product_id),
                error=str(exc),
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
            )
            if success:
                return "sent"

            backoff = 2 ** attempt
            logger.warning(
                "Email delivery failed, retrying",
                to_email=to_email,
                attempt=attempt,
                backoff_seconds=backoff,
            )
            time.sleep(backoff)

        logger.error(
            "Email delivery permanently failed",
            to_email=to_email,
            product_id=str(job.product_id),
        )
        return "failed"

    @staticmethod
    def _infer_platform(url: str) -> str:
        return "amazon" if "amazon.in" in url else "flipkart"