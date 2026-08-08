import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import select, func, text
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

    def update_url(self, product: Product, new_url: str) -> Product:
        """Overwrite the stored URL — used to backfill affiliate tags."""
        product.url = new_url
        self.db.flush()
        return product

    def update_affiliate_data(
        self,
        product: Product,
        mrp: Optional[Decimal],
        special_price: Optional[Decimal],
        discount_pct: Optional[float],
        offers: list[str],
    ) -> Product:
        """
        Persist affiliate API enrichment fields to the products row.
        Called after every successful affiliate API fetch — cron and preview.
        Only updates when values are non-None so browser-scraped results
        (which pass None) never overwrite previously stored affiliate data.
        """
        if mrp is not None:
            product.mrp = mrp
        if special_price is not None:
            product.special_price = special_price
        if discount_pct is not None:
            product.discount_pct = discount_pct
        if offers:
            product.offers = offers
        self.db.flush()
        return product

    def update_product_metadata(
        self,
        product: Product,
        metadata: dict,
    ) -> Product:
        """
        Persist merged product metadata (JSONB) to the products row.
        Called after every successful scrape when product_metadata is non-empty.
        The merge logic lives in ScraperEngine.merge_metadata() — by the time
        this method is called, existing keys have already been preserved.
        """
        product.product_metadata = metadata
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

        drop_result = self.db.execute(
            text("""
                SELECT COUNT(*) AS drop_count
                FROM (
                    SELECT
                        price,
                        LAG(price) OVER (ORDER BY checked_at ASC) AS prev_price
                    FROM price_history
                    WHERE product_id = :product_id
                    AND scrape_status = 'success'
                    AND price IS NOT NULL
                ) sub
                WHERE price < prev_price
            """),
            {"product_id": str(product_id)},
        )
        drop_count = drop_result.scalar() or 0

        return {
            "all_time_low": row.all_time_low,
            "all_time_high": row.all_time_high,
            "drop_count": drop_count,
            "first_tracked_at": row.first_tracked_at,
        }

    def update_category(self, product: Product, category: str) -> Product:
        """
        Persist the unified category slug to the products row.
        Called by scraper_worker after a successful scrape.
        """
        product.category = category
        self.db.flush()
        return product

    def get_all(
        self,
        platform: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """
        Return all products ordered by watcher_count DESC, created_at DESC.
        Includes per-product watcher count and all-time low/high from
        price_history. Used by GET /v1/products (public offers/catalogue page).

        Args:
            platform: Optional platform filter ("amazon" | "flipkart" | "myntra").
            category: Optional unified category filter ("mobiles" | "electronics" | ...).
            limit:    Max rows to return (1–100).
            offset:   Pagination offset.
        """
        # ── Watcher count per product ──────────────────────────────────────
        watcher_sq = (
            select(
                Subscription.product_id,
                func.count(Subscription.subscription_id).label("watcher_count"),
            )
            .group_by(Subscription.product_id)
            .subquery()
        )

        # ── All-time low/high per product (successful scrapes only) ────────
        stats_sq = (
            select(
                PriceHistory.product_id,
                func.min(PriceHistory.price).label("all_time_low"),
                func.max(PriceHistory.price).label("all_time_high"),
            )
            .where(
                PriceHistory.scrape_status == "success",
                PriceHistory.price.isnot(None),
            )
            .group_by(PriceHistory.product_id)
            .subquery()
        )

        watcher_count_col = func.coalesce(
            watcher_sq.c.watcher_count, 0
        ).label("watcher_count")

        q = (
            select(
                Product.product_id,
                Product.name,
                Product.image_url,
                Product.url,
                Product.platform,
                Product.current_price,
                Product.mrp,
                Product.special_price,
                Product.discount_pct,
                Product.availability,
                Product.rating,
                Product.review_count,
                Product.last_checked_at,
                Product.created_at,
                Product.category,
                watcher_count_col,
                stats_sq.c.all_time_low,
                stats_sq.c.all_time_high,
            )
            .outerjoin(watcher_sq, Product.product_id == watcher_sq.c.product_id)
            .outerjoin(stats_sq, Product.product_id == stats_sq.c.product_id)
        )

        if platform:
            q = q.where(Product.platform == platform)

        if category:
            q = q.where(Product.category == category)

        # ── Total count (without pagination) ──────────────────────────────
        count_q = select(func.count(Product.product_id))
        if platform:
            count_q = count_q.where(Product.platform == platform)
        if category:
            count_q = count_q.where(Product.category == category)
        total = self.db.scalar(count_q) or 0

        # ── Paginated results ──────────────────────────────────────────────
        rows = self.db.execute(
            q.order_by(
                func.coalesce(watcher_sq.c.watcher_count, 0).desc(),
                Product.created_at.desc(),
            )
            .limit(limit)
            .offset(offset)
        ).mappings().all()

        return [dict(r) for r in rows], total

    def get_max_prices(
        self,
        product_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, "Decimal"]:
        """
        Return the all-time maximum successful price for each product_id
        in a single batch query — no N+1.

        Used by GET /v1/items to compute price_drop_pct on dashboard cards.
        Comparing current_price against the all-time max correctly surfaces
        "price peaked then dropped" situations (not just last-scrape changes).

        Returns: {product_id: max_price}
        Products with no successful price history are absent from the dict.
        """
        if not product_ids:
            return {}

        rows = self.db.execute(
            select(
                PriceHistory.product_id,
                func.max(PriceHistory.price).label("max_price"),
            )
            .where(
                PriceHistory.product_id.in_(product_ids),
                PriceHistory.scrape_status == "success",
                PriceHistory.price.isnot(None),
            )
            .group_by(PriceHistory.product_id)
        ).all()

        return {row.product_id: row.max_price for row in rows}

    def delete(self, product: Product) -> None:
        self.db.delete(product)
        self.db.flush()
