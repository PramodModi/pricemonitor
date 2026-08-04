"""
    GenericScraper — the single scraper class for all portals.
    
    Replaces amazon.py and flipkart.py entirely.
    Portal-specific behaviour lives in portals.yaml (selectors, product ID pattern)
    and hooks.py (pre-extract page interactions).
    
    Flow per scrape:
        1. Navigate to URL
        2. Check bot detection
        3. Run pre_extract_hook if configured (e.g. dismiss Flipkart login)
        4. Extract price via LayerSelector-ordered 6-layer strategy
        5. Extract product ID, name, image, availability, rating, review count
        6. Return ScrapeResponse with full diagnostics
    
    All timing is captured at each step for observability.
"""
 
from __future__ import annotations
 
import time
import uuid
from decimal import Decimal
from typing import Optional
 
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout
 
from app.scraper_v2.core.config import settings
from app.scraper_v2.core.exceptions import (
    ScrapeBotDetectedError,
    ScrapeExtractionError,
    ScrapeTimeoutError,
)
from app.scraper_v2.core.logging import get_logger
from app.scraper_v2.models.scrape_result import ScrapeFailureReason, ScrapeResponse
from app.scraper_v2.scrapers import hooks
from app.scraper_v2.scrapers.base import BaseScraper
from app.scraper_v2.scrapers.layer_selector import DEFAULT_LAYER_ORDER, layer_stats_cache
from app.scraper_v2.scrapers.portal_config import PortalConfig
 
logger = get_logger(__name__)
 
# Bot detection indicators — checked before extraction
_BOT_INDICATORS: list[str] = [
    "api-services-support@amazon.com",
    "Enter the characters you see below",
    "Sorry, we just need to make sure you're not a robot",
    "captcha",
    "unusual traffic",
    "verify you are human",
    "robot check",
    "automated access",
]
 
# Common selectors for shared fields across portals
_COMMON_TITLE_SELECTORS = [
    "h1[itemprop='name']",
    "meta[property='og:title']",
    "h1",
]
_COMMON_IMAGE_SELECTORS = [
    ("meta[property='og:image']", "content"),
    ("meta[property='twitter:image']", "content"),
]
_COMMON_AVAILABILITY_SELECTORS = [
    "[itemprop='availability']",
    "meta[property='product:availability']",
    "link[itemprop='availability']",
]
 
 
class GenericScraper(BaseScraper):
    """
    Single scraper class for all portals.
    Instantiated once per ScraperWorker (same lifecycle as old AmazonScraper).
    """
 
    def scrape(
        self,
        page: Page,
        url: str,
        config: PortalConfig,
        job_id: Optional[str] = None,
        attempt_number: int = 1,
        worker_id: Optional[int] = None,
        skip_navigation: bool = False,
    ) -> ScrapeResponse:
        """
        Scrape one product page and return a fully populated ScrapeResponse.
 
        Args:
            page:           Fresh stealth-configured Playwright Page.
            url:            Canonical product URL.
            config:         PortalConfig from registry — selectors, hooks, etc.
            job_id:         Correlation ID from ScrapeRequest (echoed in response).
            attempt_number:   Which retry this is (1 = first attempt).
            worker_id:        Worker thread ID for diagnostics.
            skip_navigation:  When True, skip page.goto() — the caller has
                              already loaded HTML into the page via set_content()
                              (ScraperAPI path) or page.goto() to a cache URL.
                              Navigating again would overwrite the pre-loaded
                              HTML with a live bot-blocked page.
 
        Returns:
            ScrapeResponse — success=True with product data, or
            success=False with error_type and error_message.
            Diagnostic fields always populated.
        """
        job_id = job_id or str(uuid.uuid4())
        t_total_start = time.monotonic()
        nav_ms = 0
        extraction_ms = 0
 
        # Reset per-scrape JSON-LD cache (populated by Layer 2 if it succeeds)
        self._jsonld_cache: dict = {}
 
        # ── Navigation ──────────────────────────────────────────────────────
        # Note: browser engine selection (chromium vs firefox) happens at the
        # WorkerManager/run_test level — config.browser drives that decision.
        #
        # skip_navigation=True: caller pre-loaded HTML via set_content() or
        # navigated to a cache URL. Do NOT call page.goto() — that would
        # overwrite the pre-loaded HTML by navigating to the live (bot-blocked)
        # product URL, discarding the ScraperAPI/cached HTML entirely.
        if not skip_navigation:
            try:
                t_nav = time.monotonic()
                page.goto(
                    url,
                    timeout=settings.page_goto_timeout_ms,
                    wait_until=config.goto_wait_until,
                )
                nav_ms = int((time.monotonic() - t_nav) * 1000)
 
                # ── WAF challenge handling (Amazon on Railway datacenter IPs) ──
                # AWS WAF serves a JS challenge page before the real product page.
                # The challenge JS runs, gets a token, then does window.location.reload().
                # page.goto() returns on the challenge page (domcontentloaded fires there).
                # We detect the challenge and wait for the reload to complete.
                if config.name == "amazon":
                    try:
                        page_content = page.content()
                        if "awswaf" in page_content or "AwsWafIntegration" in page_content:
                            logger.info(
                                f"[NAV] portal={config.name} — AWS WAF challenge detected, "
                                f"waiting for reload — url={url}"
                            )
                            page.wait_for_load_state("load", timeout=settings.page_goto_timeout_ms)
                            page.wait_for_timeout(3000)
                            nav_ms = int((time.monotonic() - t_nav) * 1000)
                            logger.info(
                                f"[NAV] portal={config.name} — post-WAF nav_ms={nav_ms}"
                            )
                    except Exception as waf_exc:
                        logger.debug(f"[NAV] WAF check error — {waf_exc}")
 
                if config.post_nav_wait_ms > 0:
                    page.wait_for_timeout(config.post_nav_wait_ms)
                logger.info(
                    f"[NAV] portal={config.name} nav_ms={nav_ms} url={url}"
                )
            except PlaywrightTimeout:
                total_ms = int((time.monotonic() - t_total_start) * 1000)
                logger.warning(
                    f"[SCRAPE_FAIL] portal={config.name} "
                    f"status=timeout nav_ms={nav_ms} url={url}"
                )
                return ScrapeResponse(
                    success=False,
                    job_id=job_id,
                    portal=config.name,
                    total_duration_ms=total_ms,
                    navigation_ms=nav_ms,
                    attempt_number=attempt_number,
                    worker_id=worker_id,
                    error_type=ScrapeFailureReason.TIMEOUT,
                    error_message="page.goto() timed out",
                )
        else:
            logger.info(
                f"[NAV] portal={config.name} skip_navigation=True "
                f"(HTML pre-loaded by caller) url={url}"
            )
 
        # ── Bot detection ─────────────────────────────────────────────────────
        try:
            self._check_bot_detection(page, url, config.name)
        except ScrapeBotDetectedError as exc:
            total_ms = int((time.monotonic() - t_total_start) * 1000)
            logger.warning(
                f"[BOT_DETECTED] portal={config.name} "
                f"reason={exc.reason} url={url}"
            )
            return ScrapeResponse(
                success=False,
                job_id=job_id,
                portal=config.name,
                total_duration_ms=total_ms,
                navigation_ms=nav_ms,
                attempt_number=attempt_number,
                worker_id=worker_id,
                error_type=ScrapeFailureReason.BOT_DETECTED,
                error_message=exc.reason,
            )
 
        # ── Pre-extract hook ──────────────────────────────────────────────────
        if config.pre_extract_hook:
            t_hook = time.monotonic()
            hooks.run(config.pre_extract_hook, page, url=url)
            hook_ms = int((time.monotonic() - t_hook) * 1000)
            logger.debug(f"[SCRAPE] hook={config.pre_extract_hook} hook_ms={hook_ms}")
 
        # ── Price extraction (6 layers) ───────────────────────────────────────
        layer_order = self._get_layer_order(config)
        t_extraction = time.monotonic()
 
        try:
            price, method, layers_attempted, layers_failed = (
                self._extract_price_with_fallbacks(
                    page=page,
                    url=url,
                    portal_name=config.name,
                    css_selectors=config.price_selectors,
                    selector_timeout_ms=settings.page_selector_timeout_ms,
                    layer_order=layer_order,
                    skip_layers=config.skip_layers,
                )
            )
        except ScrapeExtractionError as exc:
            total_ms = int((time.monotonic() - t_total_start) * 1000)
            extraction_ms = int((time.monotonic() - t_extraction) * 1000)
            logger.error(
                f"[SCRAPE_FAIL] portal={config.name} "
                f"status=failed layers_tried={layer_order} url={url}"
            )
            return ScrapeResponse(
                success=False,
                job_id=job_id,
                portal=config.name,
                layers_attempted=layer_order,
                layers_failed=layer_order,
                total_duration_ms=total_ms,
                navigation_ms=nav_ms,
                extraction_ms=extraction_ms,
                attempt_number=attempt_number,
                worker_id=worker_id,
                error_type=ScrapeFailureReason.ALL_LAYERS_FAILED,
                error_message=exc.reason,
            )
 
        extraction_ms = int((time.monotonic() - t_extraction) * 1000)
 
        # ── Product field extraction ───────────────────────────────────────────
        product_id = self._extract_product_id(page, url, config)
        name = self._extract_name(page, config)
        brand = self._extract_brand(page, config)
        image_url = self._extract_image(page, config)
        availability = self._extract_availability(page, config)
        rating = self._extract_rating(page, config)
        review_count = self._extract_review_count(page, config)
        seller = self._extract_seller(page, config)
 
        total_ms = int((time.monotonic() - t_total_start) * 1000)
 
        logger.info(
            f"[SCRAPE_OK] portal={config.name} "
            f"method={method} "
            f"price={price} "
            f"product_id={product_id} "
            f"layers_tried={layers_attempted} "
            f"layers_failed={layers_failed} "
            f"nav_ms={nav_ms} "
            f"extraction_ms={extraction_ms} "
            f"total_ms={total_ms} "
            f"attempt={attempt_number}"
        )
 
        # ── Extended metadata extraction ──────────────────────────────────────
        product_metadata = self._extract_metadata(page, config)
 
        return ScrapeResponse(
            success=True,
            job_id=job_id,
            portal=config.name,
            marketplace_product_id=product_id,
            current_price=price,
            name=name,
            brand=brand,
            image_url=image_url,
            availability=availability,
            rating=rating,
            review_count=review_count,
            seller=seller,
            extraction_method=method,
            layers_attempted=layers_attempted,
            layers_failed=layers_failed,
            total_duration_ms=total_ms,
            navigation_ms=nav_ms,
            extraction_ms=extraction_ms,
            attempt_number=attempt_number,
            worker_id=worker_id,
            product_metadata=product_metadata,
        )
 
    # ── Bot detection ─────────────────────────────────────────────────────────
 
    def _check_bot_detection(
        self, page: Page, url: str, portal: str
    ) -> None:
        try:
            body = page.inner_text("body") or ""
        except Exception:
            return
        body_lower = body.lower()
        for indicator in _BOT_INDICATORS:
            if indicator.lower() in body_lower:
                raise ScrapeBotDetectedError(
                    url, f"Bot detection indicator found: {indicator!r}"
                )
 
    # ── Layer ordering ────────────────────────────────────────────────────────
 
    def _get_layer_order(self, config: PortalConfig) -> list[str]:
        """
        Get layer order from cache. If affiliate_api is disabled for
        this portal, remove it from the order to skip it entirely.
        """
        order = layer_stats_cache.get_layer_order(config.name)
        if not config.affiliate_api and "affiliate_api" in order:
            order = [l for l in order if l != "affiliate_api"]
        return order
 
    # ── Product ID ────────────────────────────────────────────────────────────
 
    def _extract_product_id(
        self, page: Page, url: str, config: PortalConfig
    ) -> Optional[str]:
        """
        Try current page URL first (may differ after redirects),
        then original URL. Returns None if pattern doesn't match.
        """
        for candidate in (page.url, url):
            pid = config.extract_product_id(candidate)
            if pid:
                return pid
        logger.warning(
            f"[EXTRACT] Could not extract product_id — "
            f"portal={config.name} url={url}"
        )
        return None
 
    # ── Name ─────────────────────────────────────────────────────────────────
 
    def _extract_name(self, page: Page, config: "PortalConfig") -> Optional[str]:
        # 1. Portal-specific selector (most precise — e.g. #productTitle on Amazon)
        if config.title_selector:
            text = self._extract_text(page, config.title_selector)
            if text and len(text.strip()) > 3:
                return text.strip()
 
        # 2. JSON-LD cache (populated by Layer 2 if it succeeded)
        if self._jsonld_cache.get("name"):
            import re as _re
            name = self._jsonld_cache["name"]
            truncated = bool(_re.search(r'[.…]{2,3}more$', name, flags=_re.IGNORECASE))
            if not truncated:
                return name
            # JSON-LD name is truncated by Flipkart's JS — fall through to OG title
 
        # 3. OG meta — server-rendered, contains full title
        og = self._extract_attribute(page, "meta[property='og:title']", "content")
        logger.debug(f"[NAME] og:title raw={og!r:.120}")
        if og:
            # Strip portal suffixes (e.g. "Product Name - Buy ... | Flipkart.com")
            og = og.split(" - Buy ")[0].split(" | ")[0].strip()
            if len(og) > 3:
                return og
 
        # 4. Generic H1 fallbacks
        for selector in _COMMON_TITLE_SELECTORS:
            text = self._extract_text(page, selector)
            if text and len(text.strip()) > 3:
                return text.strip()
        return None
 
    # ── Brand ─────────────────────────────────────────────────────────────────
 
    def _extract_brand(self, page: Page, config: "PortalConfig") -> Optional[str]:
        portal = config.name
 
        # 1. Portal-specific selector
        if config.brand_selector:
            raw = self._extract_text(page, config.brand_selector)
            if raw:
                for phrase in ["Visit the ", " Store", "Brand: "]:
                    raw = raw.replace(phrase, "")
                brand = raw.strip() or None
                if brand:
                    return brand
 
        # 2. JSON-LD cache (populated by Layer 2 if it succeeded)
        if self._jsonld_cache.get("brand"):
            return self._jsonld_cache["brand"]
 
        # 3. schema.org brand meta/microdata
        brand = self._extract_attribute(
            page, "meta[itemprop='brand']", "content"
        ) or self._extract_text(page, "[itemprop='brand']")
 
        if not brand and portal == "amazon":
            raw = self._extract_text(page, "#bylineInfo")
            if raw:
                for phrase in ["Visit the ", " Store", "Brand: "]:
                    raw = raw.replace(phrase, "")
                brand = raw.strip() or None
 
        return brand or None
 
    # ── Image ─────────────────────────────────────────────────────────────────
 
    def _extract_image(self, page: Page, config: "PortalConfig") -> Optional[str]:
        portal = config.name
 
        # 1. Portal-specific selector
        if config.image_selector:
            val = self._extract_attribute(page, config.image_selector, "src")
            if val and val.startswith("http"):
                return val
 
        # 2. JSON-LD cache (populated by Layer 2 if it succeeded)
        if self._jsonld_cache.get("image"):
            val = self._jsonld_cache["image"]
            if val.startswith("http"):
                return val
 
        # 3. OG / Twitter meta — reliable across all portals
        for selector, attr in _COMMON_IMAGE_SELECTORS:
            val = self._extract_attribute(page, selector, attr)
            if val and val.startswith("http"):
                return val
 
        # 4. Portal-specific pattern fallbacks
        if portal == "flipkart":
            # Large product images use rukminim2 CDN with /image/800/ path
            img = self._extract_image_by_pattern(page, "rukminim2.flixcart.com/image/800")
            if img:
                return img
 
        return None
 
    # ── Availability ──────────────────────────────────────────────────────────
 
    def _extract_availability(self, page: Page, config: "PortalConfig") -> bool:
        portal = config.name
        # JSON-LD cache (availability parsed from schema.org URL)
        if self._jsonld_cache.get("availability") is not None:
            return self._jsonld_cache["availability"]
        # schema.org availability link
        for selector in _COMMON_AVAILABILITY_SELECTORS:
            val = (
                self._extract_attribute(page, selector, "href")
                or self._extract_attribute(page, selector, "content")
                or self._extract_text(page, selector)
                or ""
            )
            if val:
                return "outofstock" not in val.lower().replace(" ", "")
 
        if portal == "amazon":
            text = self._extract_text(page, "#availability span") or ""
            return "out of stock" not in text.lower()
 
        if portal == "flipkart":
            # Presence of buy/cart action = in stock
            try:
                for el in page.query_selector_all("div, span, a, button"):
                    try:
                        text = el.inner_text().strip().lower()
                        if text in ("buy now", "add to cart"):
                            return True
                    except Exception:
                        continue
                return False
            except Exception:
                return True
 
        return True  # default to available when unknown
 
    # ── Rating ───────────────────────────────────────────────────────────────
 
    def _extract_rating(self, page: Page, config: "PortalConfig") -> Optional[Decimal]:
        portal = config.name
        # JSON-LD cache
        if self._jsonld_cache.get("rating") is not None:
            try:
                return Decimal(str(self._jsonld_cache["rating"]))
            except Exception:
                pass
        # schema.org ratingValue
        val = self._extract_attribute(
            page, "[itemprop='ratingValue']", "content"
        ) or self._extract_text(page, "[itemprop='ratingValue']")
        if val:
            return self._parse_price_safe(val)
 
        if portal == "amazon":
            import re
            text = self._extract_text(
                page, "span[data-hook='rating-out-of-text']"
            ) or ""
            m = re.search(r"(\d+\.?\d*)\s+out of", text)
            if m:
                return self._parse_price_safe(m.group(1))
 
        if portal == "flipkart":
            # Flipkart shows rating as plain number e.g. "4.3"
            text = self._extract_text(page, "div[class*='XQDdHH']") or ""
            return self._parse_price_safe(text.strip())
 
        return None
 
    # ── Review count ─────────────────────────────────────────────────────────
 
    def _extract_review_count(self, page: Page, config: "PortalConfig") -> Optional[int]:
        portal = config.name
        # JSON-LD cache
        if self._jsonld_cache.get("review_count") is not None:
            return self._jsonld_cache["review_count"]
        import re
 
        # schema.org reviewCount
        val = self._extract_attribute(
            page, "[itemprop='reviewCount']", "content"
        ) or self._extract_text(page, "[itemprop='reviewCount']")
        if val:
            cleaned = re.sub(r"[^\d]", "", val)
            return int(cleaned) if cleaned else None
 
        if portal == "amazon":
            text = self._extract_text(page, "#acrCustomerReviewText") or ""
            cleaned = re.sub(r"[^\d]", "", text)
            return int(cleaned) if cleaned else None
 
        if portal == "flipkart":
            # "based on 2,47,102 ratings by Verified Buyers"
            try:
                for el in page.query_selector_all("*"):
                    try:
                        text = el.inner_text().strip()
                        if (
                            "based on" in text.lower()
                            and "rating" in text.lower()
                            and len(text) < 80
                        ):
                            cleaned = re.sub(
                                r"[^\d]", "", text.split("ratings")[0]
                            )
                            if cleaned:
                                return int(cleaned)
                    except Exception:
                        continue
            except Exception:
                pass
 
        return None
 
    # ── Seller ───────────────────────────────────────────────────────────────
 
    def _extract_seller(self, page: Page, config: "PortalConfig") -> Optional[str]:
        # JSON-LD cache
        if self._jsonld_cache.get("seller"):
            return self._jsonld_cache["seller"]
 
        # 1. Portal-specific selector from portals.yaml
        if config.seller_selector:
            text = self._extract_text(page, config.seller_selector)
            if text:
                return text.strip()
 
        # 2. Hardcoded fallbacks (same selectors, kept for portals without yaml entry)
        portal = config.name
        if portal == "amazon":
            text = self._extract_text(page, "#sellerProfileTriggerId")
            return text.strip() if text else None
        if portal == "flipkart":
            text = self._extract_text(page, "div#sellerName span")
            return text.strip() if text else None
        return None
 
    # ── Extended metadata extraction ──────────────────────────────────────────
 
    def _extract_metadata(self, page: Page, config: "PortalConfig") -> dict:
        """
        Extract portal-specific enrichment metadata from the loaded page.
        Returns a dict (may be empty if nothing could be extracted).
        Never raises — all exceptions are caught and logged.
 
        Dispatcher routes to the portal-specific implementation.
        Keys written per portal:
          Amazon : description, images, category, subcategory, specs, features
          Flipkart: description, images, category, specs, features
          Myntra  : description, images, category, subcategory,
                    sizes_available, material, fit, style_notes, specs
        """
        portal = config.name
        try:
            if portal == "amazon":
                return self._extract_metadata_amazon(page)
            if portal == "flipkart":
                return self._extract_metadata_flipkart(page)
            if portal == "myntra":
                return self._extract_metadata_myntra(page)
        except Exception as exc:
            logger.warning(
                f"[META] metadata extraction failed — portal={portal} error={exc}"
            )
        return {}
 
    def _extract_metadata_amazon(self, page: Page) -> dict:
        """
        Extract enrichment metadata from an Amazon product page.
 
        Sources used (in priority order per field):
          - JSON-LD cache (Layer 2 — already populated during price extraction)
          - DOM selectors (reliable Amazon IDs — #productTitle, #feature-bullets,
            #productDetails_techSpec_section_1, #wayfinding-breadcrumbs_feature_div)
        """
        import re
        meta: dict = {}
 
        # ── Description ───────────────────────────────────────────────────── #
        desc = self._extract_text(page, "#productDescription")
        if not desc:
            desc = self._extract_text(page, "#aplus .a-section")
        if desc:
            desc = re.sub(r"\s+", " ", desc).strip()
            if len(desc) > 20:
                meta["description"] = desc
 
        # ── Feature bullet points ──────────────────────────────────────────── #
        try:
            bullets = []
            items = page.query_selector_all("#feature-bullets ul li span.a-list-item")
            for item in items:
                text = item.inner_text().strip()
                if text and len(text) > 5 and "Make sure this fits" not in text:
                    bullets.append(text)
            if bullets:
                meta["features"] = bullets
        except Exception:
            pass
 
        # ── Category breadcrumb ────────────────────────────────────────────── #
        try:
            crumbs = page.query_selector_all(
                "#wayfinding-breadcrumbs_feature_div ul li a"
            )
            parts = [c.inner_text().strip() for c in crumbs if c.inner_text().strip()]
            if parts:
                meta["category"] = parts[0]
                if len(parts) > 1:
                    meta["subcategory"] = parts[-1]
        except Exception:
            pass
 
        # ── Specs table ───────────────────────────────────────────────────── #
        try:
            specs: dict = {}
            # Amazon has two possible spec table IDs
            for table_id in [
                "#productDetails_techSpec_section_1 tr",
                "#productDetails_detailBullets_sections1 tr",
                "#detailBullets_feature_div li",
            ]:
                rows = page.query_selector_all(table_id)
                for row in rows:
                    try:
                        th = row.query_selector("th")
                        td = row.query_selector("td")
                        if th and td:
                            key = re.sub(r"\s+", " ", th.inner_text()).strip()
                            val = re.sub(r"\s+", " ", td.inner_text()).strip()
                            if key and val and len(key) < 80:
                                specs[key] = val
                    except Exception:
                        continue
                if specs:
                    break
            if specs:
                meta["specs"] = specs
        except Exception:
            pass
 
        # ── Additional images ─────────────────────────────────────────────── #
        try:
            images = []
            # Amazon puts thumbnails in #altImages; extract large version
            # by replacing thumbnail dimensions in the URL
            thumbs = page.query_selector_all("#altImages ul li img")
            for thumb in thumbs:
                src = thumb.get_attribute("src") or ""
                # Convert thumbnail URL to large: ._SS40_ or ._AC_US40_ → ._SL500_
                large = re.sub(r"\._[A-Z0-9_,]+_\.", "._SL500_.", src)
                if large.startswith("http") and large not in images:
                    images.append(large)
            if images:
                meta["images"] = images[:8]  # cap at 8
        except Exception:
            pass
 
        if meta:
            logger.info(
                f"[META] amazon — keys={list(meta.keys())} "
                f"specs={len(meta.get('specs', {}))} "
                f"features={len(meta.get('features', []))}"
            )
        return meta
 
    def _extract_metadata_flipkart(self, page: Page) -> dict:
        """
        Extract enrichment metadata from a Flipkart product page (browser path).
 
        Used as fallback when the affiliate API attempt (attempt 0) fails or
        is unavailable. Extracts the same fields the API would have provided
        so no information is lost when falling back to browser scraping.
 
        Sources:
          - JSON-LD cache (Layer 2 — specs sometimes embedded in schema.org)
          - DOM selectors for description, specs table, highlights, breadcrumb
        """
        import re
        meta: dict = {}
 
        # ── Description ───────────────────────────────────────────────────── #
        for selector in [
            "div._1mXcCf",          # product description container
            "div.RmoJbe",           # alternate description block
            "div[class*='description']",
        ]:
            desc = self._extract_text(page, selector)
            if desc:
                desc = re.sub(r"\s+", " ", desc).strip()
                if len(desc) > 20:
                    meta["description"] = desc
                    break
 
        # ── Highlights / features ──────────────────────────────────────────── #
        try:
            features = []
            items = page.query_selector_all("div._2418kt li")
            if not items:
                items = page.query_selector_all("ul._1xgFaf li")
            for item in items:
                text = item.inner_text().strip()
                if text and len(text) > 5:
                    features.append(text)
            if features:
                meta["features"] = features
        except Exception:
            pass
 
        # ── Specs table ───────────────────────────────────────────────────── #
        try:
            specs: dict = {}
            rows = page.query_selector_all("table._14cfVK tr, table._1s_Smc tr")
            for row in rows:
                try:
                    cells = row.query_selector_all("td")
                    if len(cells) >= 2:
                        key = re.sub(r"\s+", " ", cells[0].inner_text()).strip()
                        val = re.sub(r"\s+", " ", cells[1].inner_text()).strip()
                        if key and val and len(key) < 80:
                            specs[key] = val
                except Exception:
                    continue
            if specs:
                meta["specs"] = specs
        except Exception:
            pass
 
        # ── Category breadcrumb ────────────────────────────────────────────── #
        try:
            crumbs = page.query_selector_all("div._2whKao a, div.row._1YokD2 a")
            parts = [c.inner_text().strip() for c in crumbs if c.inner_text().strip()]
            parts = [p for p in parts if p.lower() not in ("home", "flipkart")]
            if parts:
                meta["category"] = parts[0]
                if len(parts) > 1:
                    meta["subcategory"] = parts[-1]
        except Exception:
            pass
 
        # ── Additional images ─────────────────────────────────────────────── #
        try:
            images = []
            thumbs = page.query_selector_all("li._3BTv9X img, ul._3loOK img")
            for thumb in thumbs:
                src = (
                    thumb.get_attribute("src")
                    or thumb.get_attribute("data-src")
                    or ""
                )
                # Upgrade to 800x800 — replace any resolution suffix
                import re as _re
                large = _re.sub(r"/image/\d+/", "/image/800/", src)
                if large.startswith("http") and large not in images:
                    images.append(large)
            if images:
                meta["images"] = images[:8]
        except Exception:
            pass
 
        if meta:
            logger.info(
                f"[META] flipkart — keys={list(meta.keys())} "
                f"specs={len(meta.get('specs', {}))} "
                f"features={len(meta.get('features', []))}"
            )
        return meta
 
    def _extract_metadata_myntra(self, page: Page) -> dict:
        """
        Extract enrichment metadata from a Myntra product page.
 
        Myntra is a React SPA — the richest data source is the inline JS state
        object embedded in a <script> tag. We try two approaches:
 
        Approach A (preferred): Extract from window.__mweb_init_data__ or
          __initial_state__ JS object via page.evaluate(). Returns structured
          data including sizes, specs, brand, description.
 
        Approach B (fallback): DOM selectors on the rendered HTML — less
          complete but works when JS state extraction fails.
        """
        import json
        import re
        meta: dict = {}
 
        # ── Approach A: JS state extraction ───────────────────────────────── #
        try:
            state = page.evaluate("""() => {
                // Try multiple known state variable names
                const candidates = [
                    window.__mweb_init_data__,
                    window.__initial_state__,
                    window.__INITIAL_STATE__,
                ];
                for (const s of candidates) {
                    if (s && typeof s === 'object') return s;
                }
                // Fallback: look for JSON in <script> tags
                const scripts = document.querySelectorAll('script[type="application/json"]');
                for (const sc of scripts) {
                    try {
                        const parsed = JSON.parse(sc.textContent);
                        if (parsed && (parsed.pdp || parsed.productPage)) return parsed;
                    } catch(e) {}
                }
                return null;
            }""")
 
            if state:
                meta.update(self._parse_myntra_state(state))
        except Exception as exc:
            logger.debug(f"[META] myntra JS state extraction failed — {exc}")
 
        # ── Approach B: DOM fallback (fills gaps from JS state) ───────────── #
        try:
            # Description
            if "description" not in meta:
                desc = self._extract_text(page, "p.pdp-product-description-content")
                if not desc:
                    desc = self._extract_text(page, "div.pdp-description-content")
                if desc:
                    meta["description"] = re.sub(r"\s+", " ", desc).strip()
 
            # Category breadcrumb
            if "category" not in meta:
                crumbs = page.query_selector_all("div.breadcrumbs-container a")
                parts = [c.inner_text().strip() for c in crumbs if c.inner_text().strip()]
                # Filter noise: "home", "more by <brand>", single-char entries
                _NOISE = {"home"}
                parts = [
                    p for p in parts
                    if p.lower() not in _NOISE
                    and not p.lower().startswith("more by")
                    and len(p) > 1
                ]
                if parts:
                    meta["category"] = parts[0]
                    # Only set subcategory if it's meaningfully different from category
                    if len(parts) > 1 and parts[-1] != parts[0]:
                        meta["subcategory"] = parts[-1]
 
            # Sizes
            if "sizes_available" not in meta:
                sizes = []
                size_els = page.query_selector_all(
                    "div.size-buttons-size-button, div.pdp-sizeSelectorStyles__sizeButtonsContainer button"
                )
                for el in size_els:
                    text = el.inner_text().strip()
                    aria = el.get_attribute("aria-disabled") or ""
                    if text and aria.lower() != "true":
                        sizes.append(text)
                if sizes:
                    meta["sizes_available"] = sizes
 
            # Specs from product details section
            if "specs" not in meta:
                specs: dict = {}
                rows = page.query_selector_all(
                    "div.pdp-sizeFitDesc .pdp-nameValuePair, "
                    "div.index-tableContainer tr"
                )
                for row in rows:
                    try:
                        cells = row.query_selector_all("td, .pdp-sizeFitDescContent")
                        if len(cells) >= 2:
                            key = cells[0].inner_text().strip()
                            val = cells[1].inner_text().strip()
                            if key and val:
                                specs[key] = val
                    except Exception:
                        continue
                if specs:
                    meta["specs"] = specs
 
        except Exception as exc:
            logger.debug(f"[META] myntra DOM fallback failed — {exc}")
 
        if meta:
            logger.info(
                f"[META] myntra — keys={list(meta.keys())} "
                f"sizes={len(meta.get('sizes_available', []))}"
            )
        return meta
 
    def _parse_myntra_state(self, state: dict) -> dict:
        """
        Parse the Myntra JS state object into the unified metadata schema.
        Handles multiple known state structures (mweb vs desktop variants).
        """
        import re
        meta: dict = {}
 
        # Navigate to product data — state structure varies by app version
        pdp = (
            state.get("pdp")
            or state.get("productPage")
            or state.get("product")
            or {}
        )
        product = (
            pdp.get("product")
            or pdp.get("productDetails")
            or pdp.get("data")
            or pdp
        )
 
        # ── Description ───────────────────────────────────────────────────── #
        desc = product.get("productDescription") or product.get("description") or ""
        if desc:
            desc = re.sub(r"<[^>]+>", " ", str(desc))
            desc = re.sub(r"\s+", " ", desc).strip()
            if len(desc) > 10:
                meta["description"] = desc
 
        # ── Category ──────────────────────────────────────────────────────── #
        meta_info = product.get("metaInfo") or product.get("analytics") or {}
        category = (
            product.get("category")
            or meta_info.get("category")
            or product.get("articleType")
            or ""
        )
        subcategory = (
            product.get("subCategory")
            or meta_info.get("subCategory")
            or product.get("masterCategory")
            or ""
        )
        if category:
            meta["category"] = str(category)
        if subcategory and subcategory != category:
            meta["subcategory"] = str(subcategory)
 
        # ── Images ────────────────────────────────────────────────────────── #
        try:
            images = []
            image_list = (
                product.get("media", {}).get("albums", [{}])[0].get("images", [])
                or product.get("images", [])
                or product.get("styleImages", {}).values()
            )
            for img in image_list:
                if isinstance(img, dict):
                    src = img.get("src") or img.get("secureSrc") or img.get("imageURL") or ""
                else:
                    src = str(img)
                if src and src.startswith("http"):
                    images.append(src)
            if images:
                meta["images"] = images[:8]
        except Exception:
            pass
 
        # ── Sizes ─────────────────────────────────────────────────────────── #
        try:
            sizes = []
            size_list = product.get("sizes") or product.get("sizeChart") or []
            for s in size_list:
                if isinstance(s, dict):
                    label = s.get("label") or s.get("size") or s.get("value") or ""
                    available = s.get("available", True) or s.get("inStock", True)
                    if label and available:
                        sizes.append(str(label))
                elif s:
                    sizes.append(str(s))
            if sizes:
                meta["sizes_available"] = sizes
        except Exception:
            pass
 
        # ── Specs / attributes ─────────────────────────────────────────────── #
        try:
            specs: dict = {}
            raw_specs = (
                product.get("specifications")
                or product.get("productSpecifications")
                or []
            )
            for spec_group in raw_specs:
                if isinstance(spec_group, dict):
                    group_items = spec_group.get("attributes") or spec_group.get("specifications") or []
                    for item in group_items:
                        if isinstance(item, dict):
                            key = item.get("name") or item.get("key") or ""
                            val = item.get("value") or ""
                            if key and val:
                                specs[key] = str(val)
            # Also check flat key-value spec format
            if not specs and isinstance(raw_specs, dict):
                specs = {k: str(v) for k, v in raw_specs.items() if k and v}
 
            # Material / fit / style as individual keys + inside specs
            material = product.get("material") or specs.pop("Material", None) or ""
            fit      = product.get("fit") or specs.pop("Fit", None) or ""
            style    = product.get("styleNote") or product.get("styleDescription") or ""
 
            if material:
                meta["material"] = material
            if fit:
                meta["fit"] = fit
            if style:
                meta["style_notes"] = re.sub(r"\s+", " ", style).strip()
            if specs:
                meta["specs"] = specs
        except Exception:
            pass
 
        return meta