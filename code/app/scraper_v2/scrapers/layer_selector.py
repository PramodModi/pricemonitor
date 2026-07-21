"""
LayerSelector — adaptive layer ordering.

Instead of always trying layers in fixed order, LayerSelector queries
scrape_diagnostics to find which layers are actually working for each
portal and reorders them accordingly.

Scoring formula per layer:
    score = (success_rate × SUCCESS_WEIGHT) - (speed_penalty × SPEED_WEIGHT)

    speed_penalty = normalised avg_extraction_ms across all layers (0.0–1.0)

Higher score = try this layer earlier.
When success rates are close (within 5%), the faster layer wins.

LayerStatsCache holds the computed order in memory and refreshes every
LAYER_STATS_REFRESH_MIN minutes via APScheduler (registered in main.py).

Cold start / insufficient data: falls back to DEFAULT_LAYER_ORDER from
portals.yaml context — same fixed order used in old scraper.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone
from typing import Optional

from app.scraper_v2.core.config import settings
from app.scraper_v2.core.logging import get_logger

logger = get_logger(__name__)

# Default layer order — used on cold start and when data is insufficient.
# Ordered by stability: most-stable first, most portal-specific last.
DEFAULT_LAYER_ORDER: list[str] = [
    "meta_tags",       # most stable — server-rendered OG/product tags
    "json_ld",         # stable — SEO-driven structured data
    "semantic",        # stable — itemprop, data-testid, aria-label
    "selector",        # portal CSS from portals.yaml — fast but degrades
    "heuristic",       # ₹ regex scan — reliable fallback, slower
    "affiliate_api",   # official API — perfect but portal-limited (Amazon only)
]


class LayerStatsCache:
    """
    In-memory cache of per-portal layer statistics.
    Thread-safe — workers read from multiple threads simultaneously.

    Structure:
    {
        "amazon": {
            "order": ["selector", "json_ld", "meta_tags", ...],
            "stats": {
                "selector": {"success_rate": 0.94, "avg_ms": 230, ...},
                ...
            },
            "source": "adaptive" | "default",
            "refreshed_at": datetime,
        }
    }
    """

    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}
        self._lock = threading.RLock()

    def get_layer_order(self, portal: str) -> list[str]:
        """
        Return the current best layer order for this portal.
        Falls back to DEFAULT_LAYER_ORDER if cache is empty or stale.
        """
        with self._lock:
            entry = self._cache.get(portal)
            if entry:
                return list(entry["order"])  # copy to prevent mutation
        return list(DEFAULT_LAYER_ORDER)

    def get_stats_snapshot(self, portal: str) -> Optional[dict]:
        """Return full stats entry for a portal. None if not cached."""
        with self._lock:
            return self._cache.get(portal)

    def update(self, portal: str, stats: dict[str, dict]) -> None:
        """
        Compute scored order from raw stats and update cache.
        Called by refresh() after querying scrape_diagnostics.
        """
        order = _compute_order(stats)
        source = "adaptive" if stats else "default"

        with self._lock:
            self._cache[portal] = {
                "order": order,
                "stats": stats,
                "source": source,
                "refreshed_at": datetime.now(timezone.utc),
            }

        stats_summary = {k: f"{v['success_rate']:.0%}" for k, v in stats.items()}
        logger.info(
            f"[LAYER_STATS] portal={portal} "
            f"source={source} "
            f"order={order} "
            f"stats={stats_summary}"
        )

    def refresh_all(self, portals: list[str], db_session_factory) -> None:
        """
        Query scrape_diagnostics for all portals and update cache.
        Called every LAYER_STATS_REFRESH_MIN minutes by APScheduler.

        db_session_factory: callable returning a SQLAlchemy Session,
        e.g. SessionLocal from app.core.database.
        """
        from app.scraper_v2.diagnostics.repository import ScrapeDiagnosticRepository

        logger.info(f"[LAYER_STATS] Refreshing stats — portals={portals}")
        t0 = time.monotonic()

        db = db_session_factory()
        try:
            repo = ScrapeDiagnosticRepository(db)
            for portal in portals:
                try:
                    stats = repo.get_layer_stats(
                        portal=portal,
                        lookback_days=settings.layer_stats_lookback_days,
                        min_samples=settings.layer_stats_min_samples,
                    )
                    self.update(portal, stats)
                except Exception as exc:
                    logger.warning(
                        f"[LAYER_STATS] Failed to refresh portal={portal} — {exc}"
                    )
        finally:
            db.close()

        elapsed = int((time.monotonic() - t0) * 1000)
        logger.info(f"[LAYER_STATS] Refresh complete — elapsed_ms={elapsed}")


# ── Scoring ───────────────────────────────────────────────────────────────────

def _compute_order(stats: dict[str, dict]) -> list[str]:
    """
    Score each layer and return sorted order (best first).

    Layers with insufficient data (sufficient_data=False) stay in
    their default position — not enough signal to move them.

    Layers not present in stats at all keep default position too —
    this handles new portals and new layers gracefully.
    """
    if not stats:
        return list(DEFAULT_LAYER_ORDER)

    # Normalise avg_ms across all layers for speed penalty (0.0–1.0)
    ms_values = [
        v["avg_extraction_ms"]
        for v in stats.values()
        if v["sufficient_data"] and v["avg_extraction_ms"] > 0
    ]
    max_ms = max(ms_values) if ms_values else 1.0

    scored: list[tuple[float, int, str]] = []  # (score, default_pos, layer)
    for layer in DEFAULT_LAYER_ORDER:
        default_pos = DEFAULT_LAYER_ORDER.index(layer)
        layer_stats = stats.get(layer)

        if layer_stats is None or not layer_stats["sufficient_data"]:
            # Not enough data — keep default position with neutral score
            scored.append((0.0 - default_pos * 0.001, default_pos, layer))
            continue

        success_rate = layer_stats["success_rate"]
        avg_ms = layer_stats["avg_extraction_ms"]
        speed_penalty = (avg_ms / max_ms) if max_ms > 0 else 0.0

        score = (
            success_rate * settings.layer_score_success_weight
            - speed_penalty * settings.layer_score_speed_weight
        )

        scored.append((score, default_pos, layer))

    # Sort: highest score first; break ties by default position (stable order)
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [layer for _, _, layer in scored]


# ── Module-level singleton ────────────────────────────────────────────────────

layer_stats_cache = LayerStatsCache()
