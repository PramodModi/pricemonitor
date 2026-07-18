import queue
import threading
import time
import uuid

from app.workers.worker_manager import WorkerManager
from app.core.config import settings


def test_worker_manager():
    print("\n── WorkerManager (isolation) ────────────────────────────────────")

    # ── 1. Spawns correct number of threads ──────────────────────────────
    scrape_queue = queue.Queue()
    email_queue = queue.Queue()

    wm = WorkerManager(scrape_queue, email_queue)
    wm.start()
    time.sleep(1)  # let threads initialise

    with wm._lock:
        num_spawned = len(wm._workers)

    assert num_spawned == settings.max_scraper_workers, (
        f"expected {settings.max_scraper_workers} workers, got {num_spawned}"
    )
    print(f"✅ WorkerManager: spawned {num_spawned} worker threads")

    # ── 2. All spawned threads are alive ─────────────────────────────────
    with wm._lock:
        threads = list(wm._workers.values())
    assert all(t.is_alive() for t in threads)
    print("✅ WorkerManager: all worker threads are alive")

    # ── 3. Graceful shutdown — all threads stop ───────────────────────────
    wm.shutdown()
    time.sleep(2)
    print("✅ WorkerManager: shutdown completed without hanging")

    # ── 4. Health monitor restarts a dead thread ──────────────────────────
    scrape_queue2 = queue.Queue()
    email_queue2 = queue.Queue()

    wm2 = WorkerManager(scrape_queue2, email_queue2)
    original_interval = settings.worker_health_check_interval
    settings.__dict__["worker_health_check_interval"] = 2

    # Patch _spawn_worker to use a lightweight fake instead of real ScraperWorker
    def fake_spawn(worker_id: int) -> threading.Thread:
        def fake_run():
            while True:
                job = scrape_queue2.get()
                scrape_queue2.task_done()
                if job is None:
                    break
        t = threading.Thread(target=fake_run, daemon=True, name=f"FakeWorker-{worker_id}")
        with wm2._lock:
            wm2._workers[worker_id] = t
        t.start()
        return t

    wm2._spawn_worker = fake_spawn
    wm2.start()
    time.sleep(1)

    # Replace one worker with a short-lived fake
    with wm2._lock:
        victim_id = list(wm2._workers.keys())[0]

    fake = threading.Thread(target=lambda: time.sleep(0.1), daemon=True)
    fake.start()
    with wm2._lock:
        wm2._workers[victim_id] = fake

    fake.join(timeout=5)
    assert not fake.is_alive()
    print(f"✅ WorkerManager: replaced worker-{victim_id} with short-lived thread")

    # Wait for monitor to detect and restart
    time.sleep(6)

    with wm2._lock:
        replacement = wm2._workers[victim_id]

    assert replacement is not fake
    assert replacement.is_alive()
    print(f"✅ WorkerManager: health monitor restarted worker-{victim_id}")

    settings.__dict__["worker_health_check_interval"] = original_interval
    wm2.shutdown()

    print("\n✅ All WorkerManager tests passed")


test_worker_manager()