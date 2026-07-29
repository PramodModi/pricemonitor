import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
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

    def get_for_product(
        self,
        product_id: uuid.UUID,
        limit: int = 90,
    ) -> list[PriceHistory]:
        """
        Return the last `limit` successful price rows for a product,
        ordered oldest-first (for charting).
        Only rows with scrape_status='success' and price IS NOT NULL.
        """
        stmt = (
            select(PriceHistory)
            .where(
                PriceHistory.product_id == product_id,
                PriceHistory.scrape_status == "success",
                PriceHistory.price.isnot(None),
            )
            .order_by(PriceHistory.checked_at.desc())
            .limit(limit)
        )
        rows = self.db.execute(stmt).scalars().all()
        # Reverse so chart renders oldest → newest left to right
        return list(reversed(rows))
