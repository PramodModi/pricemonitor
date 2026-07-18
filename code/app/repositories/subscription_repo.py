import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload

from app.core.models.subscription import Subscription
from app.core.models.user import User


class SubscriptionRepository:

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, subscription_id: uuid.UUID) -> Optional[Subscription]:
        return self.db.get(Subscription, subscription_id)

    def get_by_user_and_product(
        self,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> Optional[Subscription]:
        return self.db.scalar(
            select(Subscription).where(
                Subscription.user_id == user_id,
                Subscription.product_id == product_id,
            )
        )

    def get_or_create(
        self,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
    ) -> tuple[Subscription, bool]:
        existing = self.get_by_user_and_product(user_id, product_id)
        if existing:
            return existing, False
        sub = Subscription(user_id=user_id, product_id=product_id)
        self.db.add(sub)
        self.db.flush()
        return sub, True

    def get_all_for_user(self, user_id: uuid.UUID) -> list[Subscription]:
        return list(
            self.db.scalars(
                select(Subscription)
                .options(joinedload(Subscription.product))
                .where(Subscription.user_id == user_id)
                .order_by(Subscription.created_at.desc())
            )
        )

    def get_subscriber_emails_for_product(
        self,
        product_id: uuid.UUID,
    ) -> list[str]:
        rows = self.db.execute(
            select(User.email)
            .join(Subscription, Subscription.user_id == User.user_id)
            .where(Subscription.product_id == product_id)
        ).all()
        return [row.email for row in rows]

    def delete(self, subscription: Subscription) -> None:
        self.db.delete(subscription)
        self.db.flush()

    def count_for_product(self, product_id: uuid.UUID) -> int:
        return self.db.scalar(
            select(func.count(Subscription.subscription_id)).where(
                Subscription.product_id == product_id
            )
        ) or 0