import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import ForeignKey, Numeric, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class PriceHistory(Base):
    __tablename__ = "price_history"

    history_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("products.product_id", ondelete="CASCADE"),
        nullable=False,
    )
    run_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduler_runs.run_id", ondelete="RESTRICT"),
        nullable=True,
    )
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    scrape_status: Mapped[str] = mapped_column(String(20), nullable=False)
    checked_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False, server_default=text("now()")
    )

    product: Mapped["Product"] = relationship(
        "Product", back_populates="price_history"
    )
    scheduler_run: Mapped[Optional["SchedulerRun"]] = relationship(
        "SchedulerRun", back_populates="price_history_rows"
    )