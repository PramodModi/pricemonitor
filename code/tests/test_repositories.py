from decimal import Decimal
from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.repositories.user_repo import UserRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.price_history_repo import PriceHistoryRepository
from app.repositories.scheduler_run_repo import SchedulerRunRepository

def test_repositories():
    db = SessionLocal()
    try:
        # 1 — User
        user_repo = UserRepository(db)
        user, created = user_repo.get_or_create("test@example.com")
        print(f"✅ User: {user.email} (created={created})")

        # 2 — Scheduler run
        run_repo = SchedulerRunRepository(db)
        run = run_repo.create()
        print(f"✅ SchedulerRun created: {run.run_id}")

        # 3 — Product
        product_repo = ProductRepository(db)
        product = product_repo.create(
            url="https://www.amazon.in/dp/B0CHX1W1XY",
            platform="amazon",
            marketplace_product_id="B0CHX1W1XY",
            name="Apple iPhone 15 (128 GB) - Black",
            current_price=Decimal("69999.00"),
            availability=True,
        )
        print(f"✅ Product created: {product.product_id}")

        # 4 — Subscription
        sub_repo = SubscriptionRepository(db)
        sub, created = sub_repo.get_or_create(user.user_id, product.product_id)
        print(f"✅ Subscription: {sub.subscription_id} (created={created})")

        # 5 — Price history
        ph_repo = PriceHistoryRepository(db)
        ph = ph_repo.insert(
            product_id=product.product_id,
            price=Decimal("69999.00"),
            scrape_status="success",
            run_id=run.run_id,
        )
        print(f"✅ PriceHistory inserted: {ph.history_id}")

        # 6 — Complete the run
        run_repo.complete(
            run, status="completed",
            products_total=1, products_scraped=1,
            products_failed=0, price_drops_found=0,
            emails_sent=0,
        )
        print(f"✅ SchedulerRun completed: {run.status}")

        # 7 — Watcher count
        count = product_repo.get_watcher_count(product.product_id)
        print(f"✅ Watcher count: {count}")

        # 8 — Price stats
        stats = product_repo.get_price_stats(product.product_id)
        print(f"✅ Price stats: {stats}")

        db.commit()
        print("\n✅ All repository tests passed — data committed to Supabase")

    except Exception as e:
        db.rollback()
        print(f"❌ Test failed: {e}")
        raise
    finally:
        db.close()

test_repositories()