"""
Registry — maps domain names and platform names to PortalConfig instances.

Built once at import time from portals.yaml.
All lookups are O(1) dict access after that.

Usage:
    from scraper_v2.scrapers.registry import get_config, get_config_for_domain

    config = get_config("amazon")                # by platform name
    config = get_config_for_domain("amazon.in")  # by domain
"""

from __future__ import annotations

from app.scraper_v2.core.exceptions import UnsupportedPlatformError
from app.scraper_v2.core.logging import get_logger
from app.scraper_v2.scrapers.portal_config import PortalConfig, load_portal_configs

logger = get_logger(__name__)

# ── Built at import time ──────────────────────────────────────────────────────

_BY_NAME: dict[str, PortalConfig] = {}    # "amazon" → PortalConfig
_BY_DOMAIN: dict[str, PortalConfig] = {}  # "amazon.in" → PortalConfig


def _build() -> None:
    configs = load_portal_configs()
    for name, config in configs.items():
        _BY_NAME[name] = config
        for domain in config.domains:
            _BY_DOMAIN[domain.lower()] = config
    logger.info(
        f"[REGISTRY] Loaded — "
        f"portals={list(_BY_NAME.keys())} "
        f"domains={list(_BY_DOMAIN.keys())}"
    )


_build()


# ── Public API ────────────────────────────────────────────────────────────────

def get_config(platform: str) -> PortalConfig:
    """
    Return PortalConfig for a platform name (e.g. "amazon").
    Raises UnsupportedPlatformError if not in portals.yaml.
    """
    config = _BY_NAME.get(platform.lower())
    if config is None:
        raise UnsupportedPlatformError(platform)
    return config


def get_config_for_domain(domain: str) -> PortalConfig:
    """
    Return PortalConfig for a domain (e.g. "amazon.in").
    Strips www. prefix automatically.
    Raises UnsupportedPlatformError if domain not registered.
    """
    clean = domain.lower().removeprefix("www.")
    config = _BY_DOMAIN.get(clean)
    if config is None:
        raise UnsupportedPlatformError(clean)
    return config


def registered_platforms() -> list[str]:
    """All platform names currently loaded. Useful for health checks."""
    return list(_BY_NAME.keys())


def registered_domains() -> list[str]:
    """All domains currently registered."""
    return list(_BY_DOMAIN.keys())
