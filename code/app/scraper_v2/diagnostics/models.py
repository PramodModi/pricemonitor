"""
ScrapeDiagnostic ORM model.

One row per scrape attempt (retries produce multiple rows with same
scrape_job_id but different attempt_number).

Links to price_history via scrape_job_id — PriceMonitor adds
scrape_job_id to price_history so any price row can be traced
back to the full diagnostic record.

Retention: 90 days. RunManager purges older rows after each cycle.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, Column, DateTime, Integer,
    Numeric, String, Text,
)
from sqlalchemy.dialects.postgresql import UUID

try:
    # Running inside PriceMonitor — reuse existing Base
    from app.core.database import Base
except ImportError:
    # Standalone — create own Base
    from sqlalchemy.orm import declarative_base
    Base = declarative_base()


class ScrapeDiagnostic(Base):
    __tablename__ = "scrape_diagnostics"

    # ── Identity ──────────────────────────────────────────────────────────────
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    scrape_job_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
        comment="Correlation key — links to price_history.scrape_job_id",
    )
    product_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="FK to products.id — nullable for preview scrapes",
    )
    run_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
        comment="FK to scheduler_runs.id — null for preview/manual scrapes",
    )

    # ── Request context ───────────────────────────────────────────────────────
    portal = Column(String, nullable=False)   # "amazon", "flipkart"
    url = Column(Text, nullable=False)

    # ── Outcome ───────────────────────────────────────────────────────────────
    status = Column(
        String,
        nullable=False,
        comment="success | failed | blocked | timeout | config_error",
    )
    price_found = Column(Numeric(12, 2), nullable=True)
    extraction_method = Column(
        String,
        nullable=True,
        comment="meta_tags | json_ld | semantic | selector | heuristic | affiliate_api",
    )

    # ── Layer detail ──────────────────────────────────────────────────────────
    layers_attempted = Column(
        Text,
        nullable=True,
        comment="Ordered comma-separated list: meta_tags,json_ld,selector",
    )
    layers_failed = Column(
        Text,
        nullable=True,
        comment="Comma-separated layers that returned None: meta_tags,json_ld",
    )

    # ── Timing ───────────────────────────────────────────────────────────────
    total_duration_ms = Column(Integer, nullable=True)
    navigation_ms = Column(Integer, nullable=True)
    extraction_ms = Column(Integer, nullable=True)

    # ── Retry context ────────────────────────────────────────────────────────
    attempt_number = Column(Integer, nullable=False, default=1)
    worker_id = Column(Integer, nullable=True)

    # ── Error detail ─────────────────────────────────────────────────────────
    error_type = Column(
        String,
        nullable=True,
        comment="ScrapeExtractionError | ScrapeTimeoutError | ScrapeBotDetectedError",
    )
    error_message = Column(Text, nullable=True)

    # ── Timestamp ────────────────────────────────────────────────────────────
    scraped_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )

    def __repr__(self) -> str:
        return (
            f"<ScrapeDiagnostic "
            f"job={self.scrape_job_id} "
            f"portal={self.portal} "
            f"status={self.status} "
            f"method={self.extraction_method}>"
        )
