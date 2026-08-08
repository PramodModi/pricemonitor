import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Integer, Numeric, String, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID, ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("url", name="uq_products_url"),
        UniqueConstraint(
            "platform", "marketplace_product_id",
            name="uq_products_platform_marketplace_id",
        ),
    )

    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    url: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    marketplace_product_id: Mapped[str] = mapped_column(String(100), nullable=False)
    name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    current_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    currency: Mapped[str] = mapped_column(
        String(10), nullable=False, server_default="INR"
    )
    availability: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    rating: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 1), nullable=True)
    review_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    seller: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )

    # ── Affiliate API enrichment ───────────────────────────────────────────────
    mrp: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    special_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    discount_pct: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 2), nullable=True)
    offers: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text()), nullable=True)

    # ── Extended product metadata (portal-specific, variable shape) ────────────
    # Populated by affiliate API (Flipkart) and browser scraper (all portals).
    # Schema: {
    #   "description":     str,
    #   "images":          [str, ...],
    #   "category":        str,
    #   "subcategory":     str,
    #   "specs":           {key: value, ...},
    #   "features":        [str, ...],        -- Flipkart / Amazon bullet points
    #   "sizes_available": [str, ...],        -- Myntra only
    #   "material":        str,               -- Myntra only
    #   "fit":             str,               -- Myntra only
    #   "style_notes":     str,               -- Myntra only
    # }
    # Keys absent for a portal are simply missing — not null.
    # Merged on update: existing keys preserved when new scrape cannot provide them.
    # NOTE: 'metadata' is reserved by SQLAlchemy Declarative API — attribute is
    # named product_metadata; DB column name stays 'metadata' via name= param.
    product_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    # ── Unified category ───────────────────────────────────────────────────────
    # Mapped from product_metadata["category"] by CategoryMapper at scrape time.
    # One of: mobiles, electronics, fashion, home, beauty, sports, books, toys, other.
    # Default 'other' — all existing rows remain valid after migration.
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="other"
    )

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    subscriptions: Mapped[list["Subscription"]] = relationship(
        "Subscription", back_populates="product"
    )
    price_history: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="product", cascade="all, delete-orphan"
    )
    notification_logs: Mapped[list["NotificationLog"]] = relationship(
        "NotificationLog", back_populates="product", cascade="all, delete-orphan"
    )
