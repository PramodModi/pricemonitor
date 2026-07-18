import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy.orm import Session

from app.core.models.price_history import PriceHistory


class PriceHistoryRepository:

    def __init__(self, db: Session) -> None:
        self.db = db

    def insert(
        self,
        product_id: uuid.UUID,
        price: Optional[Decimal],
        scrape_status: str,
        run_id: Optional[uuid.UUID] = None,
    ) -> PriceHistory:
        row = PriceHistory(
            product_id=product_id,
            price=price,
            scrape_status=scrape_status,
            run_id=run_id,
        )
        self.db.add(row)
        self.db.flush()
        return row