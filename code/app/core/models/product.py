import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, Integer, Numeric, String, Text, TIMESTAMP, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
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