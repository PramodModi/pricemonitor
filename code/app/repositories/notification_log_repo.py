import uuid
from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.models.notification_log import NotificationLog


class NotificationLogRepository:

    def __init__(self, db: Session) -> None:
        self.db = db

    def insert(
        self,
        user_id: uuid.UUID,
        product_id: uuid.UUID,
        run_id: uuid.UUID,
        old_price: Decimal,
        new_price: Decimal,
        status: str,
    ) -> NotificationLog:
        row = NotificationLog(
            user_id=user_id,
            product_id=product_id,
            run_id=run_id,
            old_price=old_price,
            new_price=new_price,
            status=status,
        )
        self.db.add(row)
        self.db.flush()
        return row