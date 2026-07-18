import queue
import threading
import uuid
from decimal import Decimal

from app.core.database import SessionLocal
from app.core.models import PriceHistory, Subscription, SchedulerRun
from app.repositories.user_repo import UserRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.scheduler_run_repo import SchedulerRunRepository
from app.repositories.price_history_repo import PriceHistoryRepository
from app.workers.scraper_worker import ScrapeJob
from app.scheduler.run_manager import RunManager


def mock_worker(scrape_queue: queue.Queue, db_session) -> None:
    """
    Fake worker that dequeues jobs, writes a success price_history row,
    and marks the task done. No Playwright involved.
    """
    while True:
        job = scrape_queue.get()
        if job is None:
            scrape_queue.task_done()
            break
        try:
            ph_repo = PriceHistoryRepository(db_session)
            ph_repo.insert(
                product_id=job.product_id,
                price=Decimal("69999.00"),
                scrape_status="success",
                run_id=job.run_id,
            )
            db_session.commit()
        except Exception as e:
            print(f"  mock_worker error: {e}")
        finally:
            scrape_queue.task_done()


def test_run_manager():
    print("\n── RunManager ───────────────────────────────────────────────────")

    db = SessionLocal()
    user = None
    product1 = None
    product2 = None
    run_id = None

    try:
        unique = uuid.uuid4().hex[:8]

        # Create two products to simulate a real scrape cycle
        user_repo = UserRepository(db)
        product_repo = ProductRepository(db)
        sub_repo = SubscriptionRepository(db)

        user, _ = user_repo.get_or_create(f"test_run_{unique}@pricewatch-test.com")

        product1 = product_repo.create(
            url=f"https://www.amazon.in/dp/RUNTEST1{unique[:4].upper()}",
            platform="amazon",
            marketplace_product_id=f"RUNT1{unique[:5].upper()}",
            name="Test Product 1",
            current_price=Decimal("69999.00"),
            availability=True,
        )
        product2 = product_repo.create(
            url=f"https://www.amazon.in/dp/RUNTEST2{unique[:4].upper()}",
            platform="amazon",
            marketplace_product_id=f"RUNT2{unique[:5].upper()}",
            name="Test Product 2",
            current_price=Decimal("49999.00"),
            availability=True,
        )
        sub_repo.get_or_create(user.user_id, product1.product_id)
        sub_repo.get_or_create(user.user_id, product2.product_id)
        db.commit()
        print(f"✅ Created 2 test products")

        # Set up scrape queue and mock worker
        scrape_queue = queue.Queue()

        worker_thread = threading.Thread(
            target=mock_worker,
            args=(scrape_queue, db),
            daemon=True,
        )
        worker_thread.start()

        # Run the RunManager
        run_manager = RunManager(scrape_queue)
        run_manager.run()

        # Signal mock worker to stop
        scrape_queue.put(None)
        worker_thread.join(timeout=10)

        print("✅ RunManager.run() completed")

        # Verify scheduler_run row was created and completed
        run_repo = SchedulerRunRepository(db)
        db.expire_all()

        # Find the most recent run
        from sqlalchemy import select
        from app.core.models import SchedulerRun
        recent_run = db.scalar(
            select(SchedulerRun).order_by(SchedulerRun.started_at.desc())
        )
        run_id = recent_run.run_id

        assert recent_run is not None
        assert recent_run.status in ("completed", "partial")
        assert recent_run.products_total == 2
        assert recent_run.completed_at is not None
        print(f"✅ SchedulerRun created: status={recent_run.status}, total={recent_run.products_total}")

        # Verify price_history rows were written for both products
        ph_count = db.query(PriceHistory).filter(
            PriceHistory.run_id == recent_run.run_id
        ).count()
        assert ph_count == 2, f"expected 2 price_history rows, got {ph_count}"
        print(f"✅ price_history rows written: {ph_count}")

        # ── Empty catalog run ─────────────────────────────────────────────
        # Delete subscriptions and products, run again — should complete with 0
        db.query(Subscription).filter(
            Subscription.product_id.in_([product1.product_id, product2.product_id])
        ).delete()
        db.delete(product1)
        db.delete(product2)
        db.commit()
        product1 = None
        product2 = None

        scrape_queue2 = queue.Queue()
        run_manager2 = RunManager(scrape_queue2)
        run_manager2.run()

        db.expire_all()
        empty_run = db.scalar(
            select(SchedulerRun).order_by(SchedulerRun.started_at.desc())
        )
        assert empty_run.products_total == 0
        assert empty_run.status == "completed"
        print("✅ Empty catalog run: completed with products_total=0")

        print("\n✅ All RunManager tests passed")

    except Exception as e:
        db.rollback()
        print(f"❌ Test failed: {e}")
        raise

    finally:
        print("\n── Cleaning up test data ──────────────────────────────")
        try:
            if product1:
                db.query(PriceHistory).filter(
                    PriceHistory.product_id == product1.product_id
                ).delete()
                db.query(Subscription).filter(
                    Subscription.product_id == product1.product_id
                ).delete()
                db.delete(product1)
            if product2:
                db.query(PriceHistory).filter(
                    PriceHistory.product_id == product2.product_id
                ).delete()
                db.query(Subscription).filter(
                    Subscription.product_id == product2.product_id
                ).delete()
                db.delete(product2)
            if run_id:
                db.query(PriceHistory).filter(
                    PriceHistory.run_id == run_id
                ).delete()
                run = db.get(SchedulerRun, run_id)
                if run:
                    db.delete(run)
            # Clean up the empty catalog run too
            from sqlalchemy import select
            from app.core.models import SchedulerRun
            leftover_runs = db.scalars(
                select(SchedulerRun).where(
                    SchedulerRun.products_total == 0
                )
            ).all()
            for r in leftover_runs:
                db.delete(r)
            if user:
                db.delete(user)
            db.commit()
            print("✅ Test data cleaned up")
        except Exception as e:
            db.rollback()
            print(f"❌ Cleanup failed: {e}")
        finally:
            db.close()


test_run_manager()