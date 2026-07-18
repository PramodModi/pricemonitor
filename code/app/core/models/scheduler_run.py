import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, TIMESTAMP, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class SchedulerRun(Base):
    __tablename__ = "scheduler_runs"

    run_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    started_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    products_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    products_scraped: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    products_failed: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    price_drops_found: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    emails_sent: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    price_history_rows: Mapped[list["PriceHistory"]] = relationship(
        "PriceHistory", back_populates="scheduler_run"
    )
    notification_log_rows: Mapped[list["NotificationLog"]] = relationship(
        "NotificationLog", back_populates="scheduler_run"
    )