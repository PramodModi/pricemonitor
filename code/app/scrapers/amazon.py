import re
from decimal import Decimal
from typing import Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeout

from app.core.config import settings
from app.core.exceptions import ScrapeBotDetectedError, ScrapeError, ScrapeTimeoutError
from app.scrapers.base import BaseScraper, ScrapeResult
from app.utils.logging import get_logger

logger = get_logger(__name__)

_PRICE_SELECTORS = [
    "span.a-price-whole",
    "#priceblock_ourprice",
    "#priceblock_dealprice",
    ".a-price .a-offscreen",
]
_TITLE_SELECTOR = "#productTitle"
_BRAND_SELECTOR = "#bylineInfo"
_IMAGE_SELECTOR = "#landingImage"
_AVAILABILITY_SELECTOR = "#availability span"
_RATING_SELECTOR = "span[data-hook='rating-out-of-text']"
_REVIEW_COUNT_SELECTOR = "#acrCustomerReviewText"
_SELLER_SELECTOR = "#sellerProfileTriggerId"

_ASIN_PATTERN = re.compile(r"/dp/([A-Z0-9]{10})")
_BOT_INDICATORS = [
    "api-services-support@amazon.com",
    "Enter the characters you see below",
    "Sorry, we just need to make sure you're not a robot",
    "captcha",
]


class AmazonScraper(BaseScraper):

    def extract(self, page: Page, url: str) -> ScrapeResult:
        logger.info(f"Navigating to: {url}")
        try:
            page.goto(
                url,
                timeout=settings.page_goto_timeout_ms,
                wait_until="domcontentloaded",
            )
        except PlaywrightTimeout:
            raise ScrapeTimeoutError(url, "page.goto() timed out")

        self._check_bot_detection(page, url)

        price = self._extract_price(page, url)
        asin = self._extract_asin(page, url)
        name = self._extract_text(page, _TITLE_SELECTOR)
        brand = self._extract_brand(page)
        image_url = self._extract_attribute(page, _IMAGE_SELECTOR, "src")
        availability = self._extract_availability(page)
        rating = self._extract_rating(page)
        review_count = self._extract_review_count(page)
        seller = self._extract_text(page, _SELLER_SELECTOR)

        result = ScrapeResult(
            marketplace_product_id=asin,
            current_price=price,
            name=name.strip() if name else None,
            brand=brand,
            image_url=image_url,
            availability=availability,
            rating=rating,
            review_count=review_count,
            seller=seller.strip() if seller else None,
        )

        logger.info(
            f"Scraped — ASIN: {asin} | Price: ₹{price} | "
            f"Name: {(name or '')[:50]}"
        )
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _check_bot_detection(self, page: Page, url: str) -> None:
        try:
            body = page.inner_text("body") or ""
        except Exception:
            return
        for indicator in _BOT_INDICATORS:
            if indicator.lower() in body.lower():
                logger.warning(f"Bot detection triggered: {indicator}")
                raise ScrapeBotDetectedError(url, f"Bot detection: {indicator!r}")

    def _extract_price(self, page: Page, url: str) -> Decimal:
        for selector in _PRICE_SELECTORS:
            try:
                el = page.wait_for_selector(
                    selector,
                    timeout=settings.page_selector_timeout_ms,
                )
                if el:
                    raw = el.inner_text().strip()
                    raw = raw.rstrip(".")
                    return self._parse_price(raw)
            except (PlaywrightTimeout, ValueError):
                continue
        raise ScrapeError(url, "No price element found on page.")

    def _extract_asin(self, page: Page, url: str) -> str:
        for candidate in (page.url, url):
            m = _ASIN_PATTERN.search(candidate)
            if m:
                return m.group(1)
        raise ScrapeError(url, "Could not extract ASIN from URL.")

    def _extract_text(self, page: Page, selector: str) -> Optional[str]:
        try:
            el = page.query_selector(selector)
            return el.inner_text() if el else None
        except Exception:
            return None

    def _extract_attribute(
        self, page: Page, selector: str, attribute: str
    ) -> Optional[str]:
        try:
            el = page.query_selector(selector)
            return el.get_attribute(attribute) if el else None
        except Exception:
            return None

    def _extract_availability(self, page: Page) -> bool:
        text = self._extract_text(page, _AVAILABILITY_SELECTOR) or ""
        return "out of stock" not in text.lower()

    def _extract_rating(self, page: Page) -> Optional[Decimal]:
        text = self._extract_text(page, _RATING_SELECTOR) or ""
        m = re.search(r"(\d+\.?\d*)\s+out of", text)
        if m:
            try:
                return Decimal(m.group(1))
            except Exception:
                return None
        return None

    def _extract_review_count(self, page: Page) -> Optional[int]:
        text = self._extract_text(page, _REVIEW_COUNT_SELECTOR) or ""
        cleaned = re.sub(r"[^\d]", "", text)
        return int(cleaned) if cleaned else None

    def _extract_brand(self, page: Page) -> Optional[str]:
        raw = self._extract_text(page, _BRAND_SELECTOR)
        if not raw:
            return None
        for phrase in ["Visit the ", " Store", "Brand: "]:
            raw = raw.replace(phrase, "")
        return raw.strip() or None