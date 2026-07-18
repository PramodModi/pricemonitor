import queue
import threading
import uuid
from decimal import Decimal

from app.core.database import SessionLocal
from app.core.models import Product, PriceHistory, Subscription
from app.repositories.user_repo import UserRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.scheduler_run_repo import SchedulerRunRepository
from app.workers.scraper_worker import ScraperWorker, ScrapeJob


AMAZON_URL = "https://www.amazon.in/Apple-iPhone-15-128GB-Black/dp/B0CHX1W1XY"
FLIPKART_URL = "https://www.flipkart.com/apple-iphone-15/p/itm6c080842987bf"


def run_scraper_worker_test(platform: str, url: str, label: str) -> None:
    print(f"\n── ScraperWorker: {label} ────────────────────────────────────────")

    db = SessionLocal()
    user = None
    product = None
    run = None

    try:
        unique = uuid.uuid4().hex[:8]
        email = f"test_worker_{unique}@pricewatch-test.com"
        asin = f"WRKR{unique[:6].upper()}"

        user_repo = UserRepository(db)
        product_repo = ProductRepository(db)
        sub_repo = SubscriptionRepository(db)
        run_repo = SchedulerRunRepository(db)

        user, _ = user_repo.get_or_create(email)
        run = run_repo.create()
        product = product_repo.create(
            url=url,
            platform=platform,
            marketplace_product_id=asin,
            name="Test Product",
            current_price=Decimal("99999.00"),
            availability=True,
        )
        sub_repo.get_or_create(user.user_id, product.product_id)
        db.commit()
        print(f"✅ Test data created (product_id={product.product_id})")

        # Set up worker
        scrape_queue = queue.Queue()
        email_queue = queue.Queue()

        worker = ScraperWorker(
            worker_id=0,
            scrape_queue=scrape_queue,
            email_queue=email_queue,
        )

        # One real job then sentinel
        scrape_queue.put(ScrapeJob(
            product_id=product.product_id,
            url=url,
            platform=platform,
            run_id=run.run_id,
        ))
        scrape_queue.put(None)

        t = threading.Thread(target=worker.run, daemon=True)
        t.start()
        t.join(timeout=120)

        assert not t.is_alive(), "Worker thread did not finish within timeout"
        print("✅ Worker thread completed within timeout")

        # Verify price_history row
        db.expire_all()
        ph_rows = db.query(PriceHistory).filter(
            PriceHistory.product_id == product.product_id,
            PriceHistory.run_id == run.run_id,
        ).all()

        assert len(ph_rows) == 1, f"expected 1 price_history row, got {len(ph_rows)}"
        ph = ph_rows[0]

        if ph.scrape_status == "success":
            assert ph.price is not None and ph.price > 0
            print(f"✅ price_history row written: scrape_status=success, price=₹{ph.price}")
        else:
            print(f"⚠️  price_history row written: scrape_status={ph.scrape_status} "
                  f"(bot detection or network issue — row is still correct)")

        assert ph.run_id == run.run_id
        print(f"✅ price_history run_id matches")

    except Exception as e:
        db.rollback()
        print(f"❌ Test failed: {e}")
        raise

    finally:
        print("── Cleaning up test data ──────────────────────────────")
        try:
            if product:
                db.query(PriceHistory).filter(
                    PriceHistory.product_id == product.product_id
                ).delete()
                db.query(Subscription).filter(
                    Subscription.product_id == product.product_id
                ).delete()
                db.delete(product)
            if run:
                db.delete(run)
            if user:
                db.delete(user)
            db.commit()
            print("✅ Test data cleaned up")
        except Exception as e:
            db.rollback()
            print(f"❌ Cleanup failed: {e}")
        finally:
            db.close()


def test_scraper_worker():
    run_scraper_worker_test("amazon", AMAZON_URL, "Amazon")
    run_scraper_worker_test("flipkart", FLIPKART_URL, "Flipkart")
    print("\n✅ All ScraperWorker tests passed")


test_scraper_worker()