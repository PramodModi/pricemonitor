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
    Handles subscription deletion with product cleanup logic.

    When the last subscriber unsubscribes, the product record and all its
    associated price_history rows are deleted via CASCADE. This keeps the
    catalog clean — orphaned products are never retained.
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
        Remove a user's subscription. Delete the product if no subscribers remain.

        Args:
            subscription_id: The subscription to remove.
            email: Must match the subscription owner's email. Returns 404 on
                   mismatch (intentional — avoids confirming existence).

        Returns:
            UnsubscribeResult with product_deleted flag and message.

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

        remaining = self.sub_repo.count_for_product(product_id)
        product_deleted = False

        if remaining == 0:
            product = self.product_repo.get_by_id(product_id)
            if product:
                logger.info(
                    "Deleting product — no subscribers remain",
                    product_id=str(product_id),
                )
                self.product_repo.delete(product)
                product_deleted = True

        return UnsubscribeResult(
            subscription_id=subscription_id,
            product_deleted=product_deleted,
            message=(
                "Product removed and deleted from catalog (no remaining watchers)."
                if product_deleted
                else "Product removed from your tracking list."
            ),
        )