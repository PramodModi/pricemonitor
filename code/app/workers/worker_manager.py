import queue
import threading
import time
from typing import Optional

from app.core.config import settings
from app.workers.scraper_worker import ScraperWorker
from app.utils.logging import get_logger

logger = get_logger(__name__)


class WorkerManager:
    """
    Supervisor that owns the lifecycle of all ScraperWorker threads.

    Spawns exactly settings.max_scraper_workers threads at start().
    Monitors thread health every settings.worker_health_check_interval seconds.
    Restarts any dead thread immediately.
    Coordinates graceful shutdown via shutdown_event.
    """

    def __init__(
        self,
        scrape_queue: queue.Queue,
        email_queue: queue.Queue,
    ) -> None:
        self.scrape_queue = scrape_queue
        self.email_queue = email_queue
        self.shutdown_event = threading.Event()
        self._workers: dict[int, threading.Thread] = {}
        self._lock = threading.Lock()

    def start(self) -> None:
        """
        Spawn all worker threads and begin health monitoring.
        Called once at application startup.
        """
        for worker_id in range(settings.max_scraper_workers):
            self._spawn_worker(worker_id)

        monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True,
            name="WorkerManagerMonitor",
        )
        monitor_thread.start()
        logger.info(
            f"WorkerManager started - num_workers={settings.max_scraper_workers}")

    def _spawn_worker(self, worker_id: int) -> threading.Thread:
        """
        Create and start a ScraperWorker thread for the given worker_id.
        Registers the thread in the internal registry.
        """
        worker = ScraperWorker(
            worker_id=worker_id,
            scrape_queue=self.scrape_queue,
            email_queue=self.email_queue,
        )
        thread = threading.Thread(
            target=worker.run,
            daemon=True,
            name=f"ScraperWorker-{worker_id}",
        )
        with self._lock:
            self._workers[worker_id] = thread
        thread.start()
        logger.info(f"Worker spawned worker_id={worker_id}")
        return thread

    def _monitor_loop(self) -> None:
        """
        Background health-check loop. Polls every worker_health_check_interval
        seconds. Restarts any thread that is no longer alive.
        Exits when shutdown_event is set.
        """
        while not self.shutdown_event.is_set():
            time.sleep(settings.worker_health_check_interval)
            with self._lock:
                for worker_id, thread in list(self._workers.items()):
                    if not thread.is_alive():
                        logger.warning(
                            f"Worker thread died — restarting worker_id={worker_id}")
                        self._spawn_worker(worker_id)

    def shutdown(self) -> None:
        """
        Initiate graceful shutdown.
        Sends one None sentinel per worker to unblock queue.get() calls.
        Waits up to settings.queue_drain_timeout seconds for workers to finish.
        """
        logger.info("WorkerManager shutdown initiated")
        self.shutdown_event.set()

        with self._lock:
            num_workers = len(self._workers)

        for _ in range(num_workers):
            self.scrape_queue.put(None)

        with self._lock:
            threads = list(self._workers.values())

        for thread in threads:
            thread.join(timeout=settings.queue_drain_timeout)
            if thread.is_alive():
                logger.warning(
                    f"Worker did not exit within timeout - thread={thread.name}")

        logger.info("WorkerManager shutdown complete")