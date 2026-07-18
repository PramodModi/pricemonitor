import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.models.product import Product
from app.core.models.subscription import Subscription
from app.core.models.price_history import PriceHistory


class ProductRepository:

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, product_id: uuid.UUID) -> Optional[Product]:
        return self.db.get(Product, product_id)

    def get_by_platform_and_marketplace_id(
        self,
        platform: str,
        marketplace_product_id: str,
    ) -> Optional[Product]:
        return self.db.scalar(
            select(Product).where(
                Product.platform == platform,
                Product.marketplace_product_id == marketplace_product_id,
            )
        )

    def get_by_url(self, url: str) -> Optional[Product]:
        return self.db.scalar(
            select(Product).where(Product.url == url)
        )

    def create(self, **fields) -> Product:
        product = Product(**fields)
        self.db.add(product)
        self.db.flush()
        return product

    def update_from_live_data(
        self,
        product: Product,
        live_data: dict,
    ) -> Product:
        updatable_fields = [
            "name", "brand", "image_url", "availability",
            "rating", "review_count", "seller", "last_checked_at",
        ]
        for field in updatable_fields:
            if field in live_data:
                setattr(product, field, live_data[field])
        self.db.flush()
        return product

    def update_current_price(
        self,
        product: Product,
        new_price: Decimal,
    ) -> Product:
        product.current_price = new_price
        self.db.flush()
        return product

    def get_all_for_scraping(self) -> list[Product]:
        return list(
            self.db.scalars(
                select(Product).order_by(Product.created_at.asc())
            )
        )

    def get_watcher_count(self, product_id: uuid.UUID) -> int:
        return self.db.scalar(
            select(func.count(Subscription.subscription_id)).where(
                Subscription.product_id == product_id
            )
        ) or 0

    def get_price_stats(self, product_id: uuid.UUID) -> Optional[dict]:
        row = self.db.execute(
            select(
                func.min(PriceHistory.price).label("all_time_low"),
                func.max(PriceHistory.price).label("all_time_high"),
                func.min(PriceHistory.checked_at).label("first_tracked_at"),
            ).where(
                PriceHistory.product_id == product_id,
                PriceHistory.scrape_status == "success",
                PriceHistory.price.isnot(None),
            )
        ).one()

        if row.all_time_low is None:
            return None

        drop_count = self.db.scalar(
            select(func.count()).select_from(PriceHistory).where(
                PriceHistory.product_id == product_id,
                PriceHistory.scrape_status == "success",
            )
        ) or 0

        return {
            "all_time_low": row.all_time_low,
            "all_time_high": row.all_time_high,
            "drop_count": drop_count,
            "first_tracked_at": row.first_tracked_at,
        }

    def delete(self, product: Product) -> None:
        self.db.delete(product)
        self.db.flush()