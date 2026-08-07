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
        since=None,
    ) -> list[PriceHistory]:
        """
        Return successful price rows for a product, ordered oldest-first.
        Only rows with scrape_status='success' and price IS NOT NULL.

        Args:
            limit: Max rows returned (default 90). Used by get_product().
            since: Optional datetime cutoff — only rows with checked_at >= since.
                   Used by the /history endpoint for period filtering.
                   When since is set, limit is ignored (period filter is the
                   relevant constraint for the chart).
        """
        if since is not None:
            # Period-filtered path for /history endpoint — no row cap needed
            stmt = (
                select(PriceHistory)
                .where(
                    PriceHistory.product_id == product_id,
                    PriceHistory.scrape_status == "success",
                    PriceHistory.price.isnot(None),
                    PriceHistory.checked_at >= since,
                )
                .order_by(PriceHistory.checked_at.asc())
            )
            return list(self.db.execute(stmt).scalars().all())
        else:
            # Default path for get_product() — last N rows, oldest-first
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
