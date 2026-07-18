import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.core.models.scheduler_run import SchedulerRun


class SchedulerRunRepository:

    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self) -> SchedulerRun:
        run = SchedulerRun(
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        self.db.add(run)
        self.db.flush()
        return run

    def get_by_id(self, run_id: uuid.UUID) -> Optional[SchedulerRun]:
        return self.db.get(SchedulerRun, run_id)

    def complete(
        self,
        run: SchedulerRun,
        status: str,
        products_total: int,
        products_scraped: int,
        products_failed: int,
        price_drops_found: int,
        emails_sent: int,
    ) -> SchedulerRun:
        run.completed_at = datetime.now(timezone.utc)
        run.status = status
        run.products_total = products_total
        run.products_scraped = products_scraped
        run.products_failed = products_failed
        run.price_drops_found = price_drops_found
        run.emails_sent = emails_sent
        self.db.flush()
        return run

    def mark_failed(self, run: SchedulerRun) -> SchedulerRun:
        run.completed_at = datetime.now(timezone.utc)
        run.status = "failed"
        self.db.flush()
        return run

    def list_recent(
        self, limit: int = 10, offset: int = 0
    ) -> tuple[int, list[SchedulerRun]]:
        total = self.db.scalar(
            select(func.count(SchedulerRun.run_id))
        ) or 0
        runs = list(
            self.db.scalars(
                select(SchedulerRun)
                .order_by(SchedulerRun.started_at.desc())
                .limit(limit)
                .offset(offset)
            )
        )
        return total, runs