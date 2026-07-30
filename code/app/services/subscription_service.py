import uuid
from sqlalchemy.orm import Session

from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.product_repo import ProductRepository
from app.core.exceptions import SubscriptionNotFoundError
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


class SubscriptionService:
    """
    Handles subscription deletion.

    Removes only the user's subscription row. The product record and its
    full price_history are always retained — even when no subscribers remain.
    This preserves price history so it is available if the same product is
    tracked again by any user in the future.
    """

    def __init__(self, db: Session) -> None:
        self.db = db
        self.sub_repo = SubscriptionRepository(db)
        self.product_repo = ProductRepository(db)

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

        # Ownership check — 404 on mismatch (API Spec §5.4).
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
