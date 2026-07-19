import uuid
from decimal import Decimal
from sqlalchemy.orm import Session

from app.core.models import User, Product
from app.repositories.user_repo import UserRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.price_history_repo import PriceHistoryRepository
from app.services.preview_cache import ProductSnapshot
from app.core.config import settings as app_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _build_affiliated_url(url: str, platform: str) -> str:
    """Append affiliate tag to URL before storing in DB."""
    if platform == "amazon" and app_settings.amazon_affiliate_tag:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}tag={app_settings.amazon_affiliate_tag}"
    if platform == "flipkart" and app_settings.flipkart_affiliate_id:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}affid={app_settings.flipkart_affiliate_id}"
    return url

class SyncResult:
    def __init__(
        self,
        user: User,
        product: Product,
        subscription_id: uuid.UUID,
        is_new_subscription: bool,
        price_updated: bool,
    ) -> None:
        self.user = user
        self.product = product
        self.subscription_id = subscription_id
        self.is_new_subscription = is_new_subscription
        self.price_updated = price_updated


class ProductSyncService:
    """
    Orchestrates the confirm-subscription write path.

    All writes happen in a single DB transaction owned by the caller.
    This service does not commit — the router commits after sync() returns.

    run_id is always None for price_history rows written here — these are
    subscription-time writes, not scheduler-run writes (SAD §11.5).
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.product_repo = ProductRepository(db)
        self.sub_repo = SubscriptionRepository(db)
        self.ph_repo = PriceHistoryRepository(db)

    def sync(self, snapshot: ProductSnapshot, email: str) -> SyncResult:
        """
        Execute the full subscription confirm write path.

        Args:
            snapshot: ProductSnapshot consumed from the preview cache.
            email: User email — normalised to lowercase internally.

        Returns:
            SyncResult with user, product, subscription_id,
            is_new_subscription, and price_updated flag.
        """
        live = snapshot.live_data
        email = email.strip().lower()

        # Step 1 — User
        user, _ = self.user_repo.get_or_create(email)

        # Step 2 — Product upsert
        product = self.product_repo.get_by_platform_and_marketplace_id(
            live["platform"], live["marketplace_product_id"]
        )
        price_updated = False

        if product is None:
            platform=live["platform"]
            marketplace_product_id=live["marketplace_product_id"]
            logger.info(
                f"Creating new product, platform={platform} "
                f"marketplace_product_id={marketplace_product_id}"
            )
            affiliated_url = _build_affiliated_url(live["url"], live["platform"])
            product = self.product_repo.create(
                url=affiliated_url,
                platform=live["platform"],
                marketplace_product_id=live["marketplace_product_id"],
                name=live.get("name"),
                brand=live.get("brand"),
                image_url=live.get("image_url"),
                current_price=live.get("current_price"),
                availability=live.get("availability"),
                rating=live.get("rating"),
                review_count=live.get("review_count"),
                seller=live.get("seller"),
                last_checked_at=live.get("scraped_at"),
            )
            # First-ever price — write to history, no email triggered.
            self.ph_repo.insert(
                product_id=product.product_id,
                price=live.get("current_price"),
                scrape_status="success",
                run_id=None,
            )

        else:
            logger.info(
                f"Updating existing product metadata,"
                f"product_id={str(product.product_id)}"
            )
            # Step 2a — refresh mutable metadata from the live scrape.
            self.product_repo.update_from_live_data(
                product,
                {
                    "name": live.get("name"),
                    "brand": live.get("brand"),
                    "image_url": live.get("image_url"),
                    "availability": live.get("availability"),
                    "rating": live.get("rating"),
                    "review_count": live.get("review_count"),
                    "seller": live.get("seller"),
                    "last_checked_at": live.get("scraped_at"),
                },
            )

            # Step 3 — price comparison and history write.
            live_price = live.get("current_price")

            if product.current_price is None:
                # Product exists but was never successfully scraped by scheduler.
                if live_price is not None:
                    self.product_repo.update_current_price(product, live_price)
                self.ph_repo.insert(
                    product_id=product.product_id,
                    price=live_price,
                    scrape_status="success",
                    run_id=None,
                )

            elif live_price is not None and live_price != product.current_price:
                price_updated = True
                self.product_repo.update_current_price(product, live_price)
                self.ph_repo.insert(
                    product_id=product.product_id,
                    price=live_price,
                    scrape_status="success",
                    run_id=None,
                )

            else:
                # Same price — log for completeness.
                self.ph_repo.insert(
                    product_id=product.product_id,
                    price=live_price,
                    scrape_status="success",
                    run_id=None,
                )

        # Step 4 — Subscription (idempotent).
        sub, is_new = self.sub_repo.get_or_create(user.user_id, product.product_id)

        return SyncResult(
            user=user,
            product=product,
            subscription_id=sub.subscription_id,
            is_new_subscription=is_new,
            price_updated=price_updated,
        )