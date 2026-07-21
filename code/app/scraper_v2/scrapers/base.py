"""
BaseScraper — all extraction logic lives here.

Six extraction layers, tried in order determined by LayerSelector:

    Layer 1 — Meta tags          <meta property="product:price:amount">
    Layer 2 — JSON-LD            <script type="application/ld+json">
    Layer 3 — Semantic selectors [itemprop="price"], [data-testid*="price"]
    Layer 4 — Portal CSS         selectors from portals.yaml
    Layer 5 — Heuristic scan     ₹-regex over page.inner_text("body")
    Layer 6 — Affiliate API      Amazon PA-API (stub — implement on access)

Every layer returns Optional[Decimal] — None means "did not find", never raises.
ScrapeExtractionError is raised only when ALL applicable layers return None.

All shared DOM helpers (_extract_text, _extract_attribute, _parse_price)
live here so GenericScraper has zero duplication.
"""

from __future__ import annotations

import json
import re
import time
from decimal import Decimal, InvalidOperation
from typing import Optional

from playwright.sync_api import Page

from app.scraper_v2.core.exceptions import ScrapeExtractionError
from app.scraper_v2.core.logging import get_logger

logger = get_logger(__name__)

# ── Price pattern constants ───────────────────────────────────────────────────

# Matches ₹-prefixed prices including Indian lakh notation
# Examples: ₹999  ₹1,299  ₹1,29,999  ₹69,999.00
_HEURISTIC_PRICE_RE = re.compile(r"₹\s*([\d,]+(?:\.\d{1,2})?)")

# JSON-LD schema.org offer price fields
_JSONLD_PRICE_FIELDS = ("price", "lowPrice")

# Semantic selector layer — stable across redesigns
_SEMANTIC_PRICE_SELECTORS = [
    "[itemprop='price']",               # schema.org microdata
    "[itemprop='lowPrice']",
    "meta[itemprop='price']",           # meta variant
    "[data-testid*='price']",           # test IDs — rarely removed
    "[data-price]",                     # data attribute
    "[aria-label*='price' i]",          # accessibility label
    "[aria-label*='Price' i]",
    "meta[property='product:price:amount']",  # Open Graph
    "meta[property='og:price:amount']",
]

# Meta tag layer — server-rendered, never changes
_META_TAG_SELECTORS = [
    ("meta[property='product:price:amount']", "content"),
    ("meta[property='og:price:amount']", "content"),
    ("meta[name='twitter:data1']", "content"),
    ("meta[itemprop='price']", "content"),
]


class BaseScraper:
    """
    All extraction logic. GenericScraper inherits from this.
    No platform-specific code — portals.yaml handles that.
    """

    # ── Layer 1 — Meta tags ───────────────────────────────────────────────────

    def _try_meta_tags(self, page: Page) -> Optional[Decimal]:
        """
        Extract price from Open Graph / product meta tags.
        Server-rendered — present before JS executes.
        Most stable layer — survives complete layout redesigns.
        """
        for selector, attribute in _META_TAG_SELECTORS:
            try:
                el = page.query_selector(selector)
                if el:
                    val = el.get_attribute(attribute)
                    if val:
                        price = self._parse_price_safe(val)
                        if price is not None:
                            return price
            except Exception:
                continue
        return None

    # ── Layer 2 — JSON-LD structured data ─────────────────────────────────────

    def _try_structured_data(self, page: Page) -> Optional[Decimal]:
        """
        Parse JSON-LD blocks for schema.org Product/Offer price.
        SEO-driven — stable across redesigns, used by both Amazon and Flipkart.
        Also caches full product data on self._jsonld_cache for field extraction.

        Reads JSON-LD from raw page HTML (page.content()) rather than querying
        live DOM elements — some portals (Flipkart) mutate script tag content
        after load, truncating product names in the DOM while the raw HTML
        source retains the full value.
        """
        try:
            import re as _re
            raw_html = page.content()
            logger.info(f"[JSON-LD] raw_html length={len(raw_html)}")

            # Extract all application/ld+json blocks from raw HTML source
            pattern = _re.compile(
                r'<script[^>]+type=[^>]*application/ld[^>]*>(.*?)</script>',
                _re.DOTALL | _re.IGNORECASE,
            )
            matches = list(pattern.finditer(raw_html))
            logger.info(f"[JSON-LD] blocks_found={len(matches)}")

            for i, match in enumerate(matches):
                try:
                    raw_block = match.group(1)
                    logger.info(f"[JSON-LD] block={i} raw_preview={raw_block[:200].strip()!r}")
                    data = json.loads(raw_block)
                    block_type = data.get("@type", "unknown") if isinstance(data, dict) else type(data).__name__
                    logger.info(f"[JSON-LD] block={i} type={block_type!r}")
                    price, product = self._dig_jsonld_product(data)
                    logger.info(f"[JSON-LD] block={i} price={price} product_keys={list(product.keys()) if product else []}")
                    if price is not None:
                        self._jsonld_cache = product
                        logger.info(f"[JSON-LD] hit on block={i} price={price}")
                        return price
                except Exception as exc:
                    logger.info(f"[JSON-LD] block={i} exception={type(exc).__name__}: {exc}")
                    continue

            logger.info(f"[JSON-LD] no price found across {len(matches)} blocks")
        except Exception as exc:
            logger.info(f"[JSON-LD] outer exception={type(exc).__name__}: {exc}")
        return None

    def _dig_jsonld_product(
        self, data: "dict | list"
    ) -> "tuple[Optional[Decimal], dict]":
        """
        Recursively walk JSON-LD for a schema.org Product node.
        Returns (price, product_dict) where product_dict contains all
        extracted fields: name, brand, image, currency.
        Returns (None, {}) if no valid price found.
        """
        if isinstance(data, list):
            for item in data:
                price, product = self._dig_jsonld_product(item)
                if price is not None:
                    return price, product
            return None, {}

        if not isinstance(data, dict):
            return None, {}

        # Resolve offers — may be a dict or a list
        offers = data.get("offers") or data.get("Offers")
        offer_node: dict = {}
        if isinstance(offers, list) and offers:
            offer_node = offers[0]
        elif isinstance(offers, dict):
            offer_node = offers

        # Try price from offer node first, then top-level
        price: Optional[Decimal] = None
        for node in (offer_node, data):
            for field in _JSONLD_PRICE_FIELDS:
                val = node.get(field)
                if val is not None:
                    price = self._parse_price_safe(str(val))
                    if price is not None:
                        break
            if price is not None:
                break

        if price is None:
            # Recurse into nested structures (e.g. Graph nodes)
            for key in ("@graph", "mainEntity"):
                child = data.get(key)
                if child:
                    nested_price, nested_product = self._dig_jsonld_product(child)
                    if nested_price is not None:
                        return nested_price, nested_product
            return None, {}

        # Extract product-level fields
        brand = data.get("brand") or {}
        if isinstance(brand, dict):
            brand = brand.get("name", "")

        image = data.get("image") or ""
        if isinstance(image, list):
            image = image[0] if image else ""
        if isinstance(image, dict):
            image = image.get("url", "")

        currency = offer_node.get("priceCurrency") or data.get("priceCurrency", "INR")

        # Rating
        rating_node = data.get("aggregateRating") or {}
        rating = None
        review_count = None
        if isinstance(rating_node, dict):
            rv = rating_node.get("ratingValue")
            rc = rating_node.get("reviewCount") or rating_node.get("ratingCount")
            if rv is not None:
                try:
                    rating = float(rv)
                except (ValueError, TypeError):
                    pass
            if rc is not None:
                try:
                    review_count = int(rc)
                except (ValueError, TypeError):
                    pass

        # Availability — schema.org uses URL form or plain text
        availability_raw = (
            offer_node.get("availability") or data.get("availability") or ""
        )
        availability: Optional[bool] = None
        if availability_raw:
            avail_lower = str(availability_raw).lower()
            if "instock" in avail_lower or "in_stock" in avail_lower:
                availability = True
            elif "outofstock" in avail_lower or "out_of_stock" in avail_lower:
                availability = False

        # Seller — may be in offer node as "seller"
        seller_node = offer_node.get("seller") or {}
        seller = None
        if isinstance(seller_node, dict):
            seller = seller_node.get("name") or None
        elif isinstance(seller_node, str):
            seller = seller_node or None

        product = {
            "name":          str(data.get("name", "") or "").strip(),
            "brand":         str(brand or "").strip(),
            "image":         str(image or "").strip(),
            "currency":      str(currency or "INR").strip(),
            "rating":        rating,
            "review_count":  review_count,
            "availability":  availability,
            "seller":        seller,
        }
        return price, product

    # Keep old name as alias so any external callers don't break
    def _dig_jsonld_price(self, data: "dict | list") -> Optional[Decimal]:
        price, _ = self._dig_jsonld_product(data)
        return price

    # ── Layer 3 — Semantic selectors ─────────────────────────────────────────

    def _try_semantic_selectors(self, page: Page) -> Optional[Decimal]:
        """
        Try selectors based on semantic attributes — itemprop, data-testid,
        aria-label, Open Graph meta. These are added for testing and
        accessibility and rarely removed, surviving CSS class changes.
        """
        for selector in _SEMANTIC_PRICE_SELECTORS:
            try:
                el = page.query_selector(selector)
                if el:
                    # Try content attribute first (for meta tags)
                    val = el.get_attribute("content") or el.get_attribute("data-price")
                    if not val:
                        val = el.inner_text().strip()
                    if val:
                        price = self._parse_price_safe(val)
                        if price is not None:
                            return price
            except Exception:
                continue
        return None

    # ── Layer 4 — Portal CSS selectors ───────────────────────────────────────

    # Maximum wait per selector in the cascade — prevents timeouts burning
    # 5 s × 11 selectors = 55 s when elements are absent. 1500 ms is enough
    # to catch elements that need a render tick; the full timeout still applies
    # to explicit wait_for_selector calls outside the cascade.
    _SELECTOR_CASCADE_TIMEOUT_MS: int = 1500

    def _try_css_selectors(
        self,
        page: Page,
        selectors: list[str],
        timeout_ms: int,
    ) -> Optional[Decimal]:
        """
        Try each portal-specific CSS selector from portals.yaml in order.
        Uses a capped per-selector timeout (1500 ms) regardless of the
        global selector timeout — prevents 11 missing selectors × 5 s = 55 s
        worst-case waits.
        Returns None (never raises) if every selector misses.
        """
        from playwright.sync_api import TimeoutError as PlaywrightTimeout

        cascade_timeout = min(timeout_ms, self._SELECTOR_CASCADE_TIMEOUT_MS)

        for selector in selectors:
            try:
                el = page.wait_for_selector(selector, timeout=cascade_timeout)
                if el:
                    # For meta/input elements use content attribute
                    raw = (
                        el.get_attribute("content")
                        or el.get_attribute("data-price")
                        or el.inner_text().strip().rstrip(".")
                    )
                    if raw:
                        price = self._parse_price_safe(raw)
                        if price is not None:
                            return price
            except PlaywrightTimeout:
                continue
            except Exception:
                continue
        return None

    # ── Layer 5 — Heuristic regex scan ───────────────────────────────────────

    def _try_heuristic(self, page: Page) -> Optional[Decimal]:
        """
        Scan ALL visible text for ₹-shaped strings.

        Strategy: collect every ₹ match, count occurrences.
        The real buy-box price repeats most often (sticky bar, buy section,
        breadcrumb, title area). Most-frequent wins. Speed breaks ties — lower
        price is usually the actual offer price when frequencies are equal.

        Handles: ₹999  ₹1,299  ₹1,29,999  ₹69,999.00
        """
        try:
            body_text = page.inner_text("body") or ""
            matches = _HEURISTIC_PRICE_RE.findall(body_text)
            if not matches:
                return None

            frequency: dict[str, int] = {}
            for raw in matches:
                frequency[raw] = frequency.get(raw, 0) + 1

            def sort_key(raw: str) -> tuple:
                try:
                    numeric = float(raw.replace(",", ""))
                except ValueError:
                    numeric = float("inf")
                return (-frequency[raw], numeric)

            candidates = sorted(frequency.keys(), key=sort_key)
            for raw in candidates:
                price = self._parse_price_safe(raw)
                if price is not None:
                    return price
        except Exception:
            pass
        return None

    # ── Layer 6 — Affiliate API ───────────────────────────────────────────────

    def _try_affiliate_api(self, url: str, portal_name: str) -> Optional[Decimal]:
        """
        Amazon PA-API 5.0 — GetItems operation.

        Stub — implement when PA-API access is obtained.
        Returns None silently when credentials are not configured
        so the stub causes no failures.

        To implement:
            1. Set AMAZON_PAAPI_KEY, AMAZON_PAAPI_SECRET in .env
            2. pip install python-amazon-paapi5
            3. Replace the NotImplementedError block below
        """
        from scraper_v2.core.config import settings

        if not settings.amazon_paapi_key or not settings.amazon_paapi_secret:
            # Credentials not configured — skip silently
            return None

        if portal_name != "amazon":
            # Only Amazon has an affiliate API
            return None

        # TODO: implement when PA-API access received
        # from paapi5_python_sdk import ... (python-amazon-paapi5)
        logger.debug(f"[LAYER] affiliate_api — stub, skipping — url={url}")
        return None

    # ── Orchestrator ──────────────────────────────────────────────────────────

    def _extract_price_with_fallbacks(
        self,
        page: Page,
        url: str,
        portal_name: str,
        css_selectors: list[str],
        selector_timeout_ms: int,
        layer_order: list[str],
        skip_layers: list[str] | None = None,
    ) -> tuple[Decimal, str, list[str], list[str]]:
        """
        Run extraction layers in the given order (from LayerSelector).
        Layers listed in skip_layers are bypassed entirely — used for portals
        where specific layers are confirmed absent (e.g. Amazon has no JSON-LD).

        Returns:
            (price, winning_layer, layers_attempted, layers_failed)

        Raises:
            ScrapeExtractionError when all applicable layers return None.
        """
        skip = set(skip_layers or [])
        attempted: list[str] = []
        failed: list[str] = []

        layer_fns = {
            "meta_tags": lambda: self._try_meta_tags(page),
            "json_ld": lambda: self._try_structured_data(page),
            "semantic": lambda: self._try_semantic_selectors(page),
            "selector": lambda: self._try_css_selectors(
                page, css_selectors, selector_timeout_ms
            ),
            "heuristic": lambda: self._try_heuristic(page),
            "affiliate_api": lambda: self._try_affiliate_api(url, portal_name),
        }

        for layer_name in layer_order:
            if layer_name in skip:
                logger.debug(
                    f"[LAYER] portal={portal_name} layer={layer_name} status=skipped"
                )
                continue
            fn = layer_fns.get(layer_name)
            if fn is None:
                continue

            attempted.append(layer_name)
            t0 = time.monotonic()

            try:
                price = fn()
            except Exception as exc:
                logger.warning(
                    f"[LAYER] portal={portal_name} layer={layer_name} "
                    f"status=error error={exc}"
                )
                failed.append(layer_name)
                continue

            elapsed_ms = int((time.monotonic() - t0) * 1000)

            if price is not None:
                logger.info(
                    f"[LAYER] portal={portal_name} layer={layer_name} "
                    f"status=hit price={price} elapsed_ms={elapsed_ms}"
                )
                return price, layer_name, attempted, failed
            else:
                logger.debug(
                    f"[LAYER] portal={portal_name} layer={layer_name} "
                    f"status=miss elapsed_ms={elapsed_ms}"
                )
                failed.append(layer_name)

        raise ScrapeExtractionError(
            url,
            f"All layers failed — attempted={attempted}",
        )

    # ── Shared DOM helpers ────────────────────────────────────────────────────

    def _extract_text(self, page: Page, selector: str) -> Optional[str]:
        """Safely extract inner text. Returns None on any failure."""
        try:
            el = page.query_selector(selector)
            return el.inner_text() if el else None
        except Exception:
            return None

    def _extract_attribute(
        self, page: Page, selector: str, attribute: str
    ) -> Optional[str]:
        """Safely extract a DOM attribute. Returns None on any failure."""
        try:
            el = page.query_selector(selector)
            return el.get_attribute(attribute) if el else None
        except Exception:
            return None

    def _extract_image_by_pattern(
        self, page: Page, pattern: str
    ) -> Optional[str]:
        """
        Find the first <img> whose src contains the given pattern.
        Used by portal-specific image extraction (e.g. Flipkart rukminim).
        """
        try:
            for img in page.query_selector_all("img"):
                src = img.get_attribute("src") or ""
                if pattern in src:
                    return src
        except Exception:
            pass
        return None

    # ── Price parsing ─────────────────────────────────────────────────────────

    def _parse_price(self, raw: str) -> Decimal:
        """
        Convert a price string to Decimal.
        Handles: ₹69,999  ₹1,29,999  69999.00  1,299
        Raises ValueError if unparseable.
        """
        cleaned = raw.replace("₹", "").replace(",", "").strip()
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            raise ValueError(f"Cannot parse price from: {raw!r}")

    def _parse_price_safe(self, raw: str) -> Optional[Decimal]:
        """
        Same as _parse_price but returns None instead of raising.
        Used inside layer implementations where failure = try next layer.
        """
        try:
            return self._parse_price(raw)
        except (ValueError, InvalidOperation):
            return None
