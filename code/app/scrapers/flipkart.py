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
    "div.v1zwn21l.v1zwn29._1psv1zeb9._1psv1ze0._1psv1ze2c",
    "div.v1zwn21l.v1zwn20._1psv1zeb9._1psv1ze0",
    "div.Nx9bqj.CxhGGd",
    "div._30jeq3._16Jk6d",
]
_TITLE_SELECTOR = "h1"
_RATING_SELECTOR = "div.v1zwn21m.v1zwn28._1psv1zeb9._1psv1ze0._1psv1zea9._1psv1ze2c._1psv1ze4l"
_SELLER_SELECTOR = "div#sellerName span"

_PID_PATTERN = re.compile(r"/p/([a-zA-Z0-9]+)")
_BOT_INDICATORS = [
    "unusual traffic",
    "captcha",
    "verify you are human",
]


class FlipkartScraper(BaseScraper):

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

        page.wait_for_timeout(2000)
        self._dismiss_login_popup(page)
        self._check_bot_detection(page, url)

        price = self._extract_price(page, url)
        pid = self._extract_pid(page, url)
        name = self._extract_text(page, _TITLE_SELECTOR)
        image_url = self._extract_product_image(page)
        availability = self._extract_availability(page)
        rating = self._extract_rating(page)
        review_count = self._extract_review_count(page)
        seller = self._extract_text(page, _SELLER_SELECTOR)

        result = ScrapeResult(
            marketplace_product_id=pid,
            current_price=price,
            name=name.strip() if name else None,
            image_url=image_url,
            availability=availability,
            rating=rating,
            review_count=review_count,
            seller=seller.strip() if seller else None,
        )

        logger.info(
            f"Scraped — PID: {pid} | Price: ₹{price} | "
            f"Name: {(name or '')[:50]}"
        )
        return result

    # ── Private helpers ───────────────────────────────────────────────────────

    def _dismiss_login_popup(self, page: Page) -> None:
        try:
            close_selectors = [
                "button._2KpZ6l._2doB4z",
                "button[class*='_2doB4z']",
                "span._30XB9F",
            ]
            for selector in close_selectors:
                try:
                    el = page.wait_for_selector(selector, timeout=2000)
                    if el:
                        el.click()
                        page.wait_for_timeout(500)
                        return
                except PlaywrightTimeout:
                    continue
        except Exception:
            pass

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
                    return self._parse_price(raw)
            except (PlaywrightTimeout, ValueError):
                continue
        raise ScrapeError(url, "No price element found on Flipkart page.")

    def _extract_pid(self, page: Page, url: str) -> str:
        for candidate in (page.url, url):
            m = _PID_PATTERN.search(candidate)
            if m:
                return m.group(1)
        raise ScrapeError(url, "Could not extract PID from Flipkart URL.")

    def _extract_product_image(self, page: Page) -> Optional[str]:
        """
        Get the main product image — first large rukminim image (800x1070).
        Falls back to any rukminim image if the large one isn't found.
        """
        try:
            imgs = page.query_selector_all("img")
            for img in imgs:
                src = img.get_attribute("src") or ""
                if "rukminim" in src and "/800/" in src:
                    return src
            # fallback — any rukminim image
            for img in imgs:
                src = img.get_attribute("src") or ""
                if "rukminim" in src and "/image/" in src:
                    return src
        except Exception:
            pass
        return None
    
    def _extract_availability(self, page: Page) -> bool:
        """
        Flipkart uses div-based buy buttons, not <button> elements.
        Check for 'Buy Now' or 'Add to Cart' text anywhere on page.
        """
        try:
            # Look for buy action divs
            for el in page.query_selector_all("div, span, a"):
                try:
                    text = el.inner_text().strip().lower()
                    if text in ("buy now", "add to cart"):
                        return True
                except Exception:
                    continue
            return False
        except Exception:
            return True

    def _extract_rating(self, page: Page) -> Optional[Decimal]:
        try:
            el = page.query_selector(_RATING_SELECTOR)
            if el:
                text = el.inner_text().strip()
                return Decimal(text)
        except Exception:
            pass
        return None

    def _extract_review_count(self, page: Page) -> Optional[int]:
        """
        Extract review count from text like 'based on 2,47,102 ratings by Verified Buyers'.
        """
        try:
            page.evaluate("window.scrollTo(0, document.body.scrollHeight / 2)")
            page.wait_for_timeout(1500)
            page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            page.wait_for_timeout(1500)

            for el in page.query_selector_all("*"):
                try:
                    text = el.inner_text().strip()
                    if "based on" in text.lower() and "rating" in text.lower() and len(text) < 80:
                        # e.g. 'based on 2,47,102 ratings by\nVerified Buyers'
                        cleaned = re.sub(r"[^\d]", "", text.split("ratings")[0])
                        if cleaned:
                            return int(cleaned)
                except Exception:
                    continue
        except Exception:
            pass
        return None

    def _extract_text(self, page: Page, selector: str) -> Optional[str]:
        try:
            el = page.query_selector(selector)
            return el.inner_text() if el else None
        except Exception:
            return None