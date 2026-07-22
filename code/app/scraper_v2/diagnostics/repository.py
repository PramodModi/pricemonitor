"""
ScrapeDiagnosticRepository

Three responsibilities:
    1. insert()           — write one diagnostic row per scrape attempt
    2. get_layer_stats()  — aggregate stats for LayerSelector adaptive ordering
    3. purge_old()        — 90-day retention cleanup, called by RunManager
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.scraper_v2.core.logging import get_logger
from app.scraper_v2.diagnostics.models import ScrapeDiagnostic

logger = get_logger(__name__)


class ScrapeDiagnosticRepository:

    def __init__(self, db: Session) -> None:
        self._db = db

    # ── Write ─────────────────────────────────────────────────────────────────

    def insert(
        self,
        scrape_job_id: uuid.UUID,
        portal: str,
        url: str,
        status: str,
        attempt_number: int = 1,
        product_id: Optional[uuid.UUID] = None,
        run_id: Optional[uuid.UUID] = None,
        price_found: Optional[Decimal] = None,
        extraction_method: Optional[str] = None,
        layers_attempted: Optional[list[str]] = None,
        layers_failed: Optional[list[str]] = None,
        total_duration_ms: Optional[int] = None,
        navigation_ms: Optional[int] = None,
        extraction_ms: Optional[int] = None,
        worker_id: Optional[int] = None,
        error_type: Optional[str] = None,
        error_message: Optional[str] = None,
        trigger: Optional[str] = None,
        triggered_by: Optional[str] = None,
    ) -> ScrapeDiagnostic:
        """
        Write one diagnostic row. Caller commits the session.
        Lists are stored as comma-separated strings for simplicity —
        no need for a separate junction table at MVP scale.
        """
        row = ScrapeDiagnostic(
            scrape_job_id=scrape_job_id,
            product_id=product_id,
            run_id=run_id,
            portal=portal,
            url=url,
            status=status,
            price_found=price_found,
            extraction_method=extraction_method,
            layers_attempted=",".join(layers_attempted) if layers_attempted else None,
            layers_failed=",".join(layers_failed) if layers_failed else None,
            total_duration_ms=total_duration_ms,
            navigation_ms=navigation_ms,
            extraction_ms=extraction_ms,
            attempt_number=attempt_number,
            worker_id=worker_id,
            error_type=error_type,
            error_message=error_message,
            scraped_at=datetime.now(timezone.utc),
            trigger=trigger,
            triggered_by=triggered_by,
        )
        self._db.add(row)
        logger.debug(
            f"[DIAG] Queued diagnostic row — "
            f"job={scrape_job_id} portal={portal} status={status} "
            f"method={extraction_method} attempt={attempt_number} "
            f"trigger={trigger} triggered_by={triggered_by}"
        )
        return row

    # ── Read — for LayerSelector ───────────────────────────────────────────────

    def get_layer_stats(
        self,
        portal: str,
        lookback_days: int = 7,
        min_samples: int = 20,
    ) -> dict[str, dict]:
        """
        Aggregate per-layer success rate and average extraction time
        for a given portal over the lookback window.

        Returns a dict keyed by layer name:
        {
          "selector": {
              "attempts": 420,
              "successes": 395,
              "success_rate": 0.94,
              "avg_extraction_ms": 230.5,
              "sufficient_data": True,
          },
          "json_ld": { ... },
          ...
        }

        Layers with fewer than min_samples attempts are flagged
        sufficient_data=False — LayerSelector keeps them in default position.
        """
        since = datetime.now(timezone.utc) - timedelta(days=lookback_days)

        # Raw SQL for clarity — this runs every 30 minutes max, not per-request
        sql = text("""
            WITH layer_attempts AS (
                -- Unnest layers_attempted and layers_failed
                -- layers_attempted is comma-separated ordered list
                SELECT
                    d.portal,
                    d.extraction_method,
                    d.layers_attempted,
                    d.layers_failed,
                    d.extraction_ms,
                    d.status,
                    d.scraped_at
                FROM scrape_diagnostics d
                WHERE d.portal = :portal
                  AND d.scraped_at >= :since
            )
            SELECT
                extraction_method,
                COUNT(*) AS attempts,
                SUM(CASE WHEN status = 'success' THEN 1 ELSE 0 END) AS successes,
                AVG(extraction_ms) AS avg_extraction_ms
            FROM layer_attempts
            WHERE extraction_method IS NOT NULL
            GROUP BY extraction_method
        """)

        rows = self._db.execute(
            sql, {"portal": portal, "since": since}
        ).fetchall()

        stats: dict[str, dict] = {}
        for row in rows:
            attempts = row.attempts or 0
            successes = row.successes or 0
            stats[row.extraction_method] = {
                "attempts": attempts,
                "successes": successes,
                "success_rate": round(successes / attempts, 4) if attempts > 0 else 0.0,
                "avg_extraction_ms": round(float(row.avg_extraction_ms or 0), 1),
                "sufficient_data": attempts >= min_samples,
            }

        logger.debug(
            f"[DIAG] layer_stats — portal={portal} "
            f"lookback_days={lookback_days} layers={list(stats.keys())}"
        )
        return stats

    # ── Retention ─────────────────────────────────────────────────────────────

    def purge_old(self, retention_days: int = 90) -> int:
        """
        Delete diagnostic rows older than retention_days.
        Called by RunManager after each scraper cycle.
        Returns count of deleted rows.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        result = self._db.execute(
            text("DELETE FROM scrape_diagnostics WHERE scraped_at < :cutoff"),
            {"cutoff": cutoff},
        )
        deleted = result.rowcount
        if deleted > 0:
            logger.info(
                f"[DIAG] Purged old diagnostics — "
                f"deleted={deleted} retention_days={retention_days}"
            )
        return deleted
