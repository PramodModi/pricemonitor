"""
Portal configuration — loads portals.yaml into typed PortalConfig objects.

Adding a new portal:
    1. Add entry to portals.yaml
    2. Optionally add a pre_extract_hook function to hooks.py
    3. Done — no Python changes needed in scraper code
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from app.scraper_v2.core.exceptions import ScrapeConfigError
from app.scraper_v2.core.logging import get_logger

logger = get_logger(__name__)

_YAML_PATH = Path(__file__).parent / "portals.yaml"


@dataclass(frozen=True)
class PortalConfig:
    """
    All configuration for one portal (e.g. amazon, flipkart).
    Loaded from portals.yaml at import time.
    """
    name: str                              # "amazon", "flipkart"
    domains: list[str]                     # ["amazon.in", "amzn.in"]
    product_id_pattern: str                # regex with one capture group
    price_selectors: list[str]             # Layer 4 CSS selectors
    affiliate_api: bool = False            # Layer 6 enabled for this portal
    pre_extract_hook: Optional[str] = None # function name in hooks.py or None
    # Portal-specific field selectors — tried before generic fallbacks
    title_selector: Optional[str] = None
    brand_selector: Optional[str] = None
    image_selector: Optional[str] = None
    seller_selector: Optional[str] = None
    # Override page load wait strategy (default: domcontentloaded)
    goto_wait_until: str = "domcontentloaded"
    # Browser engine to use: "chromium" (default) or "firefox"
    # Some portals (Myntra) block headless Chromium via TLS fingerprinting
    # but allow Firefox headless
    browser: str = "chromium"
    # Layers to skip entirely for this portal — confirmed absent via dump analysis.
    # Skipping saves time otherwise spent on timeouts and empty results.
    skip_layers: list = field(default_factory=list)
    post_nav_wait_ms: int = 0

    # Compiled once at load time — not stored in yaml
    _id_pattern: re.Pattern = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # frozen=True means we need object.__setattr__ to set computed fields
        try:
            pattern = re.compile(self.product_id_pattern)
        except re.error as exc:
            raise ScrapeConfigError(
                f"Invalid product_id_pattern for portal '{self.name}': {exc}"
            )
        object.__setattr__(self, "_id_pattern", pattern)

    def extract_product_id(self, url: str) -> Optional[str]:
        """
        Extract the marketplace product ID from a URL.
        Returns None if the pattern does not match.
        """
        m = self._id_pattern.search(url)
        return m.group(1) if m else None


def load_portal_configs(yaml_path: Path = _YAML_PATH) -> dict[str, PortalConfig]:
    """
    Parse portals.yaml and return a mapping of portal_name → PortalConfig.
    Raises ScrapeConfigError on any structural problem.
    """
    if not yaml_path.exists():
        raise ScrapeConfigError(f"portals.yaml not found at {yaml_path}")

    try:
        with yaml_path.open("r", encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as exc:
        raise ScrapeConfigError(f"portals.yaml is invalid YAML: {exc}")

    portals_raw = raw.get("portals", {})
    if not portals_raw:
        raise ScrapeConfigError("portals.yaml has no 'portals' key or is empty")

    configs: dict[str, PortalConfig] = {}
    for name, data in portals_raw.items():
        _validate_portal_entry(name, data)
        configs[name] = PortalConfig(
            name=name,
            domains=data["domains"],
            product_id_pattern=data["product_id_pattern"],
            price_selectors=data.get("price_selectors", []),
            affiliate_api=data.get("affiliate_api", False),
            pre_extract_hook=data.get("pre_extract_hook"),
            title_selector=data.get("title_selector"),
            brand_selector=data.get("brand_selector"),
            image_selector=data.get("image_selector"),
            seller_selector=data.get("seller_selector"),
            goto_wait_until=data.get("goto_wait_until", "domcontentloaded"),
            browser=data.get("browser", "chromium"),
            skip_layers=data.get("skip_layers", []),
            post_nav_wait_ms=data.get("post_nav_wait_ms", 0),
        )
        logger.info(
            f"[CONFIG] Loaded portal — name={name} "
            f"domains={data['domains']} "
            f"selectors={len(data.get('price_selectors', []))} "
            f"affiliate_api={data.get('affiliate_api', False)} "
            f"hook={data.get('pre_extract_hook')}"
        )

    return configs


def _validate_portal_entry(name: str, data: dict) -> None:
    """Raise ScrapeConfigError if a required field is missing."""
    required = ("domains", "product_id_pattern")
    for field_name in required:
        if field_name not in data:
            raise ScrapeConfigError(
                f"Portal '{name}' in portals.yaml is missing required "
                f"field '{field_name}'"
            )
    if not isinstance(data["domains"], list) or not data["domains"]:
        raise ScrapeConfigError(
            f"Portal '{name}': 'domains' must be a non-empty list"
        )
