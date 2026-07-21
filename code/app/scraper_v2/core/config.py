"""
Scraper configuration.

When embedded in PriceMonitor: reads from app.core.config.settings
so all timeouts stay in sync with the rest of the app.

When standalone: reads directly from environment variables with
sensible defaults so run_test.py works without any setup.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ScraperConfig:
    # Playwright timeouts
    page_goto_timeout_ms: int
    page_selector_timeout_ms: int

    # Retry
    scrape_retry_limit: int

    # Layer selector
    layer_stats_lookback_days: int       # how many days of history to use
    layer_stats_min_samples: int         # minimum samples before adapting order
    layer_stats_refresh_interval_min: int  # how often to refresh cache (minutes)

    # Scoring weights for adaptive layer ordering
    layer_score_success_weight: float    # 0.0–1.0
    layer_score_speed_weight: float      # 0.0–1.0 (penalty for slowness)

    # Affiliate API (Layer 6) — stub until credentials obtained
    amazon_paapi_key: str
    amazon_paapi_secret: str
    amazon_paapi_partner_tag: str
    amazon_paapi_region: str

    # Diagnostics DB — same Supabase instance for now
    database_url: str

    # Retention
    diagnostics_retention_days: int


def _int(key: str, default: int) -> int:
    return int(os.getenv(key, default))


def _float(key: str, default: float) -> float:
    return float(os.getenv(key, default))


def _str(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def load_config() -> ScraperConfig:
    """
    Load config from PriceMonitor settings if available,
    otherwise fall back to environment variables.
    """
    try:
        from app.core.config import settings as pm
        return ScraperConfig(
            page_goto_timeout_ms=pm.page_goto_timeout_ms,
            page_selector_timeout_ms=pm.page_selector_timeout_ms,
            scrape_retry_limit=pm.scrape_retry_limit,
            layer_stats_lookback_days=_int("LAYER_STATS_LOOKBACK_DAYS", 7),
            layer_stats_min_samples=_int("LAYER_STATS_MIN_SAMPLES", 20),
            layer_stats_refresh_interval_min=_int("LAYER_STATS_REFRESH_MIN", 30),
            layer_score_success_weight=_float("LAYER_SCORE_SUCCESS_WEIGHT", 0.7),
            layer_score_speed_weight=_float("LAYER_SCORE_SPEED_WEIGHT", 0.3),
            amazon_paapi_key=_str("AMAZON_PAAPI_KEY"),
            amazon_paapi_secret=_str("AMAZON_PAAPI_SECRET"),
            amazon_paapi_partner_tag=_str("AMAZON_AFFILIATE_TAG"),
            amazon_paapi_region=_str("AMAZON_PAAPI_REGION", "in"),
            database_url=pm.database_url,
            diagnostics_retention_days=_int("DIAGNOSTICS_RETENTION_DAYS", 90),
        )
    except ImportError:
        # Standalone mode — read everything from env
        return ScraperConfig(
            page_goto_timeout_ms=_int("PAGE_GOTO_TIMEOUT_MS", 30000),
            page_selector_timeout_ms=_int("PAGE_SELECTOR_TIMEOUT_MS", 5000),
            scrape_retry_limit=_int("SCRAPE_RETRY_LIMIT", 3),
            layer_stats_lookback_days=_int("LAYER_STATS_LOOKBACK_DAYS", 7),
            layer_stats_min_samples=_int("LAYER_STATS_MIN_SAMPLES", 20),
            layer_stats_refresh_interval_min=_int("LAYER_STATS_REFRESH_MIN", 30),
            layer_score_success_weight=_float("LAYER_SCORE_SUCCESS_WEIGHT", 0.7),
            layer_score_speed_weight=_float("LAYER_SCORE_SPEED_WEIGHT", 0.3),
            amazon_paapi_key=_str("AMAZON_PAAPI_KEY"),
            amazon_paapi_secret=_str("AMAZON_PAAPI_SECRET"),
            amazon_paapi_partner_tag=_str("AMAZON_AFFILIATE_TAG"),
            amazon_paapi_region=_str("AMAZON_PAAPI_REGION", "in"),
            database_url=_str("DATABASE_URL"),
            diagnostics_retention_days=_int("DIAGNOSTICS_RETENTION_DAYS", 90),
        )


# Module-level singleton — imported everywhere inside scraper_v2
settings = load_config()
