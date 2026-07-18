from decimal import Decimal
from datetime import datetime, timezone, timedelta
import uuid

from app.core.database import SessionLocal
from app.core.models import Product, PriceHistory, Subscription
from app.core.exceptions import (
    InvalidURLError,
    UnsupportedPlatformError,
    PreviewNotFoundError,
    SubscriptionNotFoundError,
)
from app.services.url_validator import URLValidator
from app.services.preview_cache import PreviewCache, ProductSnapshot
from app.services.product_sync import ProductSyncService
from app.services.subscription_service import SubscriptionService


def make_snapshot(
    marketplace_product_id: str,
    url: str,
    price: Decimal = Decimal("69999.00"),
    expired: bool = False,
) -> ProductSnapshot:
    expires_at = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
        if expired
        else datetime.now(timezone.utc) + timedelta(minutes=10)
    )
    return ProductSnapshot(
        preview_id=uuid.uuid4(),
        expires_at=expires_at,
        is_new_product=True,
        live_data={
            "marketplace_product_id": marketplace_product_id,
            "url": url,
            "platform": "amazon",
            "name": "Apple iPhone 15 (128 GB) - Black",
            "brand": "Apple",
            "image_url": "https://m.media-amazon.com/images/I/example.jpg",
            "current_price": price,
            "currency": "INR",
            "availability": True,
            "rating": Decimal("4.5"),
            "review_count": 12483,
            "seller": "Appario Retail Private Ltd",
            "scraped_at": datetime.now(timezone.utc),
        },
    )


def test_services():
    db = SessionLocal()

    # Track everything created so cleanup is reliable
    user_a = None
    user_b = None
    product = None
    product_id_for_unsub_test = None

    # Use unique identifiers so re-runs don't collide
    unique = uuid.uuid4().hex[:8]
    EMAIL_A = f"test_svc_a_{unique}@pricewatch-test.com"
    EMAIL_B = f"test_svc_b_{unique}@pricewatch-test.com"
    TEST_ASIN = f"TSVC{unique[:6].upper()}"
    TEST_URL = f"https://www.amazon.in/Test-Product/dp/{TEST_ASIN}"

    try:
        # ── 1. URLValidator — valid Amazon /dp/ URL ───────────────────────
        v = URLValidator()
        result = v.validate(
            "https://www.amazon.in/Apple-iPhone-15/dp/B0CHX1W1XY?ref=sr&tag=xyz"
        )
        assert result.platform == "amazon"
        assert result.marketplace_product_id == "B0CHX1W1XY"
        assert "ref=" not in result.canonical_url
        assert "tag=" not in result.canonical_url
        print("✅ URLValidator: Amazon /dp/ URL — ASIN extracted, tracking params stripped")

        # ── 2. URLValidator — valid Amazon /gp/product/ URL ──────────────
        result = v.validate("https://www.amazon.in/gp/product/B0CHX1W1XY")
        assert result.marketplace_product_id == "B0CHX1W1XY"
        print("✅ URLValidator: Amazon /gp/product/ URL — ASIN extracted")

        # ── 3. URLValidator — amzn.in short URL ──────────────────────────
        result = v.validate("https://amzn.in/d/abc123")
        assert result.platform == "amazon"
        assert result.marketplace_product_id == ""
        print("✅ URLValidator: amzn.in short URL — marketplace_product_id empty")

        # ── 4. URLValidator — valid Flipkart URL ─────────────────────────
        result = v.validate(
            "https://www.flipkart.com/apple-iphone-15/p/itm123abc456?affid=xyz"
        )
        assert result.platform == "flipkart"
        assert result.marketplace_product_id == "itm123abc456"
        assert "affid=" not in result.canonical_url
        print("✅ URLValidator: Flipkart URL — PID extracted, tracking params stripped")

        # ── 5. URLValidator — known unsupported domain ────────────────────
        try:
            v.validate("https://www.croma.com/some-product/p/12345")
            raise AssertionError("Expected UnsupportedPlatformError")
        except UnsupportedPlatformError:
            print("✅ URLValidator: croma.com raises UnsupportedPlatformError")

        # ── 6. URLValidator — unknown domain ─────────────────────────────
        try:
            v.validate("https://www.randomshop.com/product/123")
            raise AssertionError("Expected InvalidURLError")
        except InvalidURLError:
            print("✅ URLValidator: unknown domain raises InvalidURLError")

        # ── 7. URLValidator — Amazon URL with no /dp/ ─────────────────────
        try:
            v.validate("https://www.amazon.in/s?k=iphone")
            raise AssertionError("Expected InvalidURLError")
        except InvalidURLError:
            print("✅ URLValidator: Amazon search URL raises InvalidURLError")

        # ── 8. URLValidator — bad scheme ──────────────────────────────────
        try:
            v.validate("ftp://www.amazon.in/dp/B0CHX1W1XY")
            raise AssertionError("Expected InvalidURLError")
        except InvalidURLError:
            print("✅ URLValidator: ftp:// raises InvalidURLError")

        # ── 9. URLValidator — empty string ────────────────────────────────
        try:
            v.validate("")
            raise AssertionError("Expected InvalidURLError")
        except InvalidURLError:
            print("✅ URLValidator: empty string raises InvalidURLError")

        # ── 10. PreviewCache — store and get ─────────────────────────────
        cache = PreviewCache()
        snap = make_snapshot(TEST_ASIN, TEST_URL)
        cache.store(snap)
        retrieved = cache.get(str(snap.preview_id))
        assert retrieved.preview_id == snap.preview_id
        print("✅ PreviewCache: store + get returns correct snapshot")

        # ── 11. PreviewCache — get on missing key ────────────────────────
        try:
            cache.get(str(uuid.uuid4()))
            raise AssertionError("Expected PreviewNotFoundError")
        except PreviewNotFoundError:
            print("✅ PreviewCache: get on missing key raises PreviewNotFoundError")

        # ── 12. PreviewCache — consume removes entry ──────────────────────
        consumed = cache.consume(str(snap.preview_id))
        assert consumed.preview_id == snap.preview_id
        try:
            cache.consume(str(snap.preview_id))
            raise AssertionError("Expected PreviewNotFoundError")
        except PreviewNotFoundError:
            print("✅ PreviewCache: consume removes entry, second consume raises error")

        # ── 13. PreviewCache — is_expired ────────────────────────────────
        fresh = make_snapshot(TEST_ASIN, TEST_URL, expired=False)
        expired = make_snapshot(TEST_ASIN, TEST_URL, expired=True)
        assert fresh.is_expired() is False
        assert expired.is_expired() is True
        print("✅ PreviewCache: is_expired works correctly")

        # ── 14. PreviewCache — purge_expired ─────────────────────────────
        cache2 = PreviewCache()
        fresh1 = make_snapshot(TEST_ASIN, TEST_URL)
        exp1 = make_snapshot(TEST_ASIN, TEST_URL, expired=True)
        exp2 = make_snapshot(TEST_ASIN, TEST_URL, expired=True)
        for s in (fresh1, exp1, exp2):
            cache2.store(s)
        removed = cache2.purge_expired()
        assert removed == 2
        cache2.get(str(fresh1.preview_id))  # still there
        try:
            cache2.get(str(exp1.preview_id))
            raise AssertionError("Expected PreviewNotFoundError")
        except PreviewNotFoundError:
            pass
        print("✅ PreviewCache: purge_expired removes 2 expired, leaves 1 fresh")

        # ── 15. ProductSyncService — new product, new user ────────────────
        sync_svc = ProductSyncService(db)
        snap1 = make_snapshot(TEST_ASIN, TEST_URL, price=Decimal("69999.00"))
        result1 = sync_svc.sync(snap1, EMAIL_A)
        db.commit()

        user_a = result1.user
        product = result1.product
        assert result1.product.platform == "amazon"
        assert result1.product.marketplace_product_id == TEST_ASIN
        assert result1.product.current_price == Decimal("69999.00")
        assert result1.is_new_subscription is True
        assert result1.price_updated is False
        print(f"✅ ProductSyncService: new product + new user created (product_id={product.product_id})")

        # ── 16. ProductSyncService — price_history row written ────────────
        ph_rows = db.query(PriceHistory).filter(
            PriceHistory.product_id == product.product_id
        ).all()
        assert len(ph_rows) == 1
        assert ph_rows[0].scrape_status == "success"
        assert ph_rows[0].run_id is None
        print("✅ ProductSyncService: price_history row written with run_id=None")

        # ── 17. ProductSyncService — duplicate subscription silent ─────────
        snap2 = make_snapshot(TEST_ASIN, TEST_URL, price=Decimal("69999.00"))
        result2 = sync_svc.sync(snap2, EMAIL_A)
        db.commit()
        assert result2.is_new_subscription is False
        assert result2.product.product_id == product.product_id
        print("✅ ProductSyncService: duplicate subscription silently succeeds")

        # ── 18. ProductSyncService — price drop updates current_price ──────
        snap3 = make_snapshot(TEST_ASIN, TEST_URL, price=Decimal("64999.00"))
        result3 = sync_svc.sync(snap3, EMAIL_A)
        db.commit()
        assert result3.product.current_price == Decimal("64999.00")
        assert result3.price_updated is True
        ph_rows2 = db.query(PriceHistory).filter(
            PriceHistory.product_id == product.product_id
        ).all()
        assert len(ph_rows2) == 3
        print("✅ ProductSyncService: price drop updates current_price, price_updated=True, 3 history rows")

        # ── 19. ProductSyncService — second user shares same product ───────
        snap4 = make_snapshot(TEST_ASIN, TEST_URL, price=Decimal("64999.00"))
        result4 = sync_svc.sync(snap4, EMAIL_B)
        db.commit()
        user_b = result4.user
        assert result4.product.product_id == product.product_id
        assert result4.is_new_subscription is True
        sub_count = db.query(Subscription).filter(
            Subscription.product_id == product.product_id
        ).count()
        assert sub_count == 2
        print("✅ ProductSyncService: second user shares same product, 2 subscriptions")

        # ── 20. SubscriptionService — wrong email raises error ────────────
        sub_svc = SubscriptionService(db)
        sub_a = db.query(Subscription).filter(
            Subscription.user_id == user_a.user_id,
            Subscription.product_id == product.product_id,
        ).first()
        try:
            sub_svc.unsubscribe(sub_a.subscription_id, "wrong@email.com")
            raise AssertionError("Expected SubscriptionNotFoundError")
        except SubscriptionNotFoundError:
            print("✅ SubscriptionService: wrong email raises SubscriptionNotFoundError")

        # ── 21. SubscriptionService — missing subscription_id raises error ─
        try:
            sub_svc.unsubscribe(uuid.uuid4(), EMAIL_A)
            raise AssertionError("Expected SubscriptionNotFoundError")
        except SubscriptionNotFoundError:
            print("✅ SubscriptionService: missing subscription_id raises SubscriptionNotFoundError")

        # ── 22. SubscriptionService — first unsub leaves product intact ────
        result_unsub_a = sub_svc.unsubscribe(sub_a.subscription_id, EMAIL_A)
        db.commit()
        assert result_unsub_a.product_deleted is False
        product_check = db.get(Product, product.product_id)
        assert product_check is not None
        print("✅ SubscriptionService: first unsubscribe leaves product intact")

        # ── 23. SubscriptionService — last unsub deletes product + cascade ─
        sub_b = db.query(Subscription).filter(
            Subscription.user_id == user_b.user_id,
            Subscription.product_id == product.product_id,
        ).first()
        result_unsub_b = sub_svc.unsubscribe(sub_b.subscription_id, EMAIL_B)
        db.commit()
        assert result_unsub_b.product_deleted is True
        product_gone = db.get(Product, product.product_id)
        assert product_gone is None
        ph_gone = db.query(PriceHistory).filter(
            PriceHistory.product_id == product.product_id
        ).count()
        assert ph_gone == 0
        product = None  # already deleted, skip cleanup
        print("✅ SubscriptionService: last unsubscribe deletes product + cascade deletes price_history")

        print("\n✅ All service tests passed")

    except Exception as e:
        db.rollback()
        print(f"❌ Test failed: {e}")
        raise

    finally:
        print("\n── Cleaning up test data ──────────────────────────────")
        try:
            if product:
                db.delete(product)
            if user_a:
                db.delete(user_a)
            if user_b:
                db.delete(user_b)
            db.commit()
            print("✅ Test data cleaned up")
        except Exception as e:
            db.rollback()
            print(f"❌ Cleanup failed: {e}")
        finally:
            db.close()


test_services()