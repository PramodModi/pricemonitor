import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, TIMESTAMP, UniqueConstraint, text
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

    # ── Resolved canonical URL (v4.9) ─────────────────────────────────────────
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """
    Clean resolved desktop URL for scraping.
    Set by URLResolver at preview time. NULL for products created before v4.9.
    Cron scraper uses this in preference to `url` (which has affiliate params).
    """

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
    # NOTE: 'metadata' is reserved by SQLAlchemy Declarative API — attribute is
    # named product_metadata; DB column name stays 'metadata' via name= param.
    product_metadata: Mapped[Optional[dict]] = mapped_column("metadata", JSONB, nullable=True)

    # ── Unified category ───────────────────────────────────────────────────────
    category: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="other"
    )

    # ── Product Identity Graph (v5.0) ──────────────────────────────────────────
    canonical_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("canonical_products.canonical_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    """
    FK to canonical_products. Links this portal listing to the real-world product
    it represents. NULL for products created before v5.0 — backfilled on next
    successful scrape via ProductIdentityService.find_or_create_canonical().

    ondelete=SET NULL: if a canonical_product row is deleted (shouldn't happen
    in normal operation), the listing becomes unlinked rather than cascade-deleted.
    """

    model_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    """
    Manufacturer model number extracted from product_metadata["specs"] at scrape
    time. e.g. "SM-S921BZDGINS", "AH8050-002", "MU7N3HN/A".

    Stored here (on the listing) as well as on canonical_products so it can be
    extracted and compared without a JOIN when processing a new scrape result.
    Also used as the signal to trigger cross-portal matching:
        SELECT canonical_id FROM products
        WHERE model_number = :model_number AND platform != :platform
    """

    normalized_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """
    Product name with variant specs stripped.
    e.g. "Samsung Galaxy S24 5G" from "SAMSUNG Galaxy S24 5G (8GB, 128GB) | AI Phone"

    Stored for:
      1. Display on canonical product cards (consistent across portals)
      2. Fuzzy name-similarity matching when model_number is absent (fashion, etc.)
      3. PostgreSQL trigram search index (v5.1)
    """

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    # ── Relationships ──────────────────────────────────────────────────────────
    canonical_product: Mapped[Optional["CanonicalProduct"]] = relationship(
        "CanonicalProduct", back_populates="listings"
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
