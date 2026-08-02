import uuid
from decimal import Decimal
from sqlalchemy.orm import Session

from app.core.models import User, Product
from app.repositories.user_repo import UserRepository
from app.repositories.product_repo import ProductRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.services.preview_cache import ProductSnapshot
from app.core.config import settings as app_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _build_affiliated_url(url: str, platform: str) -> str:
    """
    Append affiliate tag to URL before storing in DB.

    Amazon: appends ?tag= or &tag=
    Flipkart: appends affid= and affExtParam1= (both required for app + web
              tracking). The URL is already in deep link format
              (dl.flipkart.com/dl/...) by the time it arrives here —
              url_validator._canonicalise_flipkart() rewrites it upstream.
    """
    if platform == "amazon" and app_settings.amazon_affiliate_tag:
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}tag={app_settings.amazon_affiliate_tag}"
    if platform == "flipkart" and app_settings.flipkart_affiliate_id:
        affid = app_settings.flipkart_affiliate_id
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}affid={affid}&affExtParam1={affid}"
    return url


class SyncResult:
    def __init__(
        self,
        user: User,
        product: Product,
        subscription_id: uuid.UUID,
        is_new_subscription: bool,
    ) -> None:
        self.user = user
        self.product = product
        self.subscription_id = subscription_id
        self.is_new_subscription = is_new_subscription


class ProductSyncService:
    """
    Orchestrates the confirm-subscription write path.

    Product data is written to DB at preview time (products.py PATH B).
    This service only handles User + Subscription — no product create/update.

    All writes happen in a single DB transaction owned by the caller.
    This service does not commit — the router commits after sync() returns.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.user_repo = UserRepository(db)
        self.product_repo = ProductRepository(db)
        self.sub_repo = SubscriptionRepository(db)

    def sync(self, snapshot: ProductSnapshot, email: str) -> SyncResult:
        """
        Execute the confirm-subscription write path.

        Product is already in DB (written at preview time).
        This method:
          1. Gets or creates the User row
          2. Looks up the Product by platform + marketplace_product_id
          3. Gets or creates the Subscription row

        Args:
            snapshot: ProductSnapshot consumed from the preview cache.
            email: User email — normalised to lowercase internally.

        Returns:
            SyncResult with user, product, subscription_id,
            is_new_subscription flag.
        """
        live = snapshot.live_data
        email = email.strip().lower()

        # Step 1 — User
        user, _ = self.user_repo.get_or_create(email)

        # Step 2 — Product lookup
        # Product was written to DB at preview time — should always be found.
        # Fallback log if missing (should not happen in normal flow).
        product = self.product_repo.get_by_platform_and_marketplace_id(
            live["platform"], live["marketplace_product_id"]
        )
        if product is None:
            logger.warning(
                f"[SYNC] Product not found in DB at confirm time — "
                f"platform={live['platform']} "
                f"marketplace_product_id={live['marketplace_product_id']} — "
                f"this should not happen; product should have been written at preview"
            )
            raise ValueError(
                f"Product {live['marketplace_product_id']} not found in DB. "
                f"Please try previewing the product again."
            )

        # Step 3 — Subscription (idempotent)
        sub, is_new = self.sub_repo.get_or_create(user.user_id, product.product_id)

        return SyncResult(
            user=user,
            product=product,
            subscription_id=sub.subscription_id,
            is_new_subscription=is_new,
        )
