"""
CanonicalProduct — one row per real-world product, across all portals.

File: app/core/models/canonical_product.py

Relationship to products table:
    canonical_products  1 ──── * products
    (one real product)         (one listing per portal)

A CanonicalProduct represents the physical product — e.g. "Samsung Galaxy S24
5G (8GB, 128GB)". The products table represents where it is sold — Amazon, Flipkart,
or Myntra. The same physical product can appear on all three portals simultaneously,
each with a different marketplace_product_id and different price.

Cross-portal matching uses:
    1. model_number (exact)    — most reliable for electronics/footwear
    2. isbn (exact)            — books only
    3. brand + normalized_name similarity (fuzzy, threshold 0.85) — fallback

normalized_name is the product name with variant specs stripped:
    "SAMSUNG Galaxy S24 5G (Cobalt Violet, 128 GB) (8 GB RAM)"
    → "Samsung Galaxy S24 5G"

This is stored here (not on products) because it represents the product identity,
not a portal-specific listing detail.
"""

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Text, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class CanonicalProduct(Base):
    __tablename__ = "canonical_products"

    canonical_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )

    # ── Identity fields ────────────────────────────────────────────────────────
    normalized_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """
    Product name with variant specs stripped.
    e.g. "Samsung Galaxy S24 5G" not "SAMSUNG Galaxy S24 5G (8GB, 128GB Cobalt Violet)"
    Used for display and fuzzy cross-portal matching.
    """

    brand: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    """Brand name, normalized to title case. e.g. "Samsung", "Nike", "boAt"."""

    category: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="other"
    )
    """
    Unified category slug. Copied from the first portal listing that creates
    this canonical product. One of: mobiles, electronics, fashion, home,
    beauty, sports, books, toys, other.
    """

    image_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    """Best available product image. Updated when a higher-quality image is found."""

    # ── Cross-portal match keys ────────────────────────────────────────────────
    model_number: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    """
    Manufacturer model number extracted from product specs.
    e.g. "SM-S921BZDGINS" (Samsung), "AH8050-002" (Nike), "MU7N3HN/A" (Apple)

    This is the primary cross-portal match key for electronics and footwear.
    Two portal listings with the same model_number are the same physical product.

    Indexed for fast lookup. NULL for categories where model numbers don't exist
    (fashion, home decor, etc.).
    """

    isbn: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    """
    ISBN-13 or ISBN-10 for books. Exact cross-portal match key.
    NULL for non-book categories.
    """

    # ── Timestamps ────────────────────────────────────────────────────────────
    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False,
        server_default=text("now()"),
        onupdate=datetime.utcnow,
    )

    # ── Relationships ─────────────────────────────────────────────────────────
    listings: Mapped[list["Product"]] = relationship(
        "Product", back_populates="canonical_product"
    )
