import uuid
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.product_repo import ProductRepository
from app.core.models.user import User
from app.core.exceptions import SubscriptionNotFoundError, ProductNotFoundError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class UnsubscribeResult:
    def __init__(
        self,
        subscription_id: uuid.UUID,
        product_deleted: bool,
        message: str,
    ) -> None:
        self.subscription_id = subscription_id
        self.product_deleted = product_deleted
        self.message = message


class DirectSubscribeResult:
    def __init__(
        self,
        subscription_id: uuid.UUID,
        is_new_subscription: bool,
        product,
    ) -> None:
        self.subscription_id     = subscription_id
        self.is_new_subscription = is_new_subscription
        self.product             = product


class SubscriptionService:
    """
    Handles subscription creation and deletion.

    subscribe_direct — creates a subscription for a product already in the DB
                       without requiring a scrape or preview token.
    unsubscribe      — removes a subscription. Product and price history are
                       always retained even when no subscribers remain.
    """

    def __init__(self, db: Session) -> None:
        self.db           = db
        self.sub_repo     = SubscriptionRepository(db)
        self.product_repo = ProductRepository(db)

    # ── Internal helpers ──────────────────────────────────────────────────

    def _get_or_create_user(self, email: str) -> User:
        """Get existing user by email or create a new one. Caller owns flush."""
        normalised = email.strip().lower()
        user = self.db.scalar(
            select(User).where(User.email == normalised)
        )
        if user is None:
            user = User(email=normalised)
            self.db.add(user)
            self.db.flush()
        return user

    # ── Direct subscription (no scrape required) ──────────────────────────

    def subscribe_direct(
        self,
        product_id: uuid.UUID,
        email: str,
    ) -> DirectSubscribeResult:
        """
        Create (or silently confirm existing) subscription for a product
        already in the DB. No scrape or preview token required.

        Used by POST /v1/subscriptions/direct — called from the /offers page
        "Monitor this" button where the product is already known.

        Args:
            product_id: Must reference an existing product row.
            email:      Subscriber email — stored and matched lowercase.

        Returns:
            DirectSubscribeResult with subscription_id, is_new_subscription,
            and the product ORM object.

        Raises:
            ProductNotFoundError: product_id does not exist in DB.
        """
        product = self.product_repo.get_by_id(product_id)
        if product is None:
            raise ProductNotFoundError(str(product_id))

        user = self._get_or_create_user(email)

        subscription, is_new = self.sub_repo.get_or_create(
            user_id=user.user_id,
            product_id=product.product_id,
        )

        logger.info(
            f"[DIRECT_SUBSCRIBE] "
            f"product_id={product.product_id} "
            f"email={user.email} "
            f"is_new={is_new}"
        )

        return DirectSubscribeResult(
            subscription_id=subscription.subscription_id,
            is_new_subscription=is_new,
            product=product,
        )

    # ── Unsubscribe ───────────────────────────────────────────────────────

    def unsubscribe(
        self,
        subscription_id: uuid.UUID,
        email: str,
    ) -> UnsubscribeResult:
        """
        Remove a user's subscription. Product and price history are never deleted.

        Args:
            subscription_id: The subscription to remove.
            email: Must match the subscription owner's email. Returns 404 on
                   mismatch (intentional — avoids confirming existence).

        Returns:
            UnsubscribeResult with product_deleted=False and message.

        Raises:
            SubscriptionNotFoundError: subscription_id does not exist, or
                                       email does not match the owner.
        """
        subscription = self.sub_repo.get_by_id(subscription_id)

        if subscription is None:
            raise SubscriptionNotFoundError(str(subscription_id))

        if subscription.user.email != email.strip().lower():
            raise SubscriptionNotFoundError(str(subscription_id))

        product_id = subscription.product_id
        self.sub_repo.delete(subscription)

        logger.info(
            f"Subscription deleted — "
            f"subscription_id={str(subscription_id)} "
            f"product_id={str(product_id)} "
            f"product and price history retained"
        )

        return UnsubscribeResult(
            subscription_id=subscription_id,
            product_deleted=False,
            message="Product removed from your tracking list.",
        )
