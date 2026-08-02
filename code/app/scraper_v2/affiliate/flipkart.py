# app/scraper_v2/affiliate/flipkart.py
#
# Flipkart Affiliate API client — concrete implementation of BaseAffiliateClient.
#
# API used: GET /affiliate/1.0/product.json?query=<PID>
# Host:     https://affiliate-api.flipkart.net
# Auth:     HTTP headers — Fk-Affiliate-Id + Fk-Affiliate-Token (no token exchange)
#
# Required config keys (app/core/config.py → Settings):
#   flipkart_affiliate_id    : your tracking ID (already exists from v2.9)
#   flipkart_affiliate_token : API token from affiliate.flipkart.com dashboard
#
# Required env vars (Railway Variables + .env):
#   FLIPKART_AFFILIATE_ID=your_tracking_id     (already set)
#   FLIPKART_AFFILIATE_TOKEN=your_api_token    (new — add this)
#
# Product ID extraction:
#   Primary:  ?pid=BCHDAH9QHFTH5GRZ  (query param — most reliable)
#   Fallback: /p/itm62f0f8b3c0bfb    (path segment — works for canonical URLs)
#
# Response schema (v1.0):
#   productInfoList[0].productBaseInfoV1.{
#     productId, title, flipkartSellingPrice, maximumRetailPrice,
#     flipkartSpecialPrice, discountPercentage, inStock, imageUrls,
#     productBrand, offers, codAvailable
#   }
#   productInfoList[0].productShippingInfoV1.{ sellerName }

import logging
import re
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import parse_qs, urlparse

import requests

from app.core.config import settings
from app.scraper_v2.affiliate.base import BaseAffiliateClient
from app.scraper_v2.affiliate.exceptions import (
    AffiliateAuthError,
    AffiliateError,
    AffiliateNotFoundError,
    AffiliateRateLimitError,
    AffiliateTimeoutError,
)
from app.scraper_v2.affiliate.result import AffiliateResult

logger = logging.getLogger(__name__)

# ── Constants ──────────────────────────────────────────────────────────────── #

_API_BASE = "https://affiliate-api.flipkart.net/affiliate"
_PRODUCT_ENDPOINT = "/1.0/product.json"

# Matches /p/itm{alphanumeric} in the URL path.
# Covers both www.flipkart.com and dl.flipkart.com/dl/ URL forms.
_PID_FROM_PATH = re.compile(r"/p/(itm[a-zA-Z0-9]+)", re.IGNORECASE)

_REQUEST_TIMEOUT_S: int = 10
"""Seconds before requests.get() raises requests.Timeout."""


class FlipkartAffiliateClient(BaseAffiliateClient):
    """
    Flipkart Affiliate API client.

    Authentication model:
        Flipkart uses static header-based auth — no token exchange, no expiry.
        _authenticate() validates that both config keys are non-empty and builds
        self._headers. It is called once at startup and again on timeout/auth
        errors (the re-auth path) in case credentials were rotated in config.

    Retry behaviour (inherited from BaseAffiliateClient):
        Up to 3 attempts. Delays: 1s → 2s.
        AffiliateTimeoutError / AffiliateAuthError → re-auth once, then retry.
        AffiliateNotFoundError → return None immediately (not retriable).
        AffiliateRateLimitError → wait 30s, then retry.

    Data freshness:
        The Flipkart affiliate feed is updated periodically (not real-time).
        If the API returns a price that differs significantly from the live
        page, the discrepancy will be corrected at the next cron scrape.
        For price monitoring purposes, API data is used as-is.
    """

    def __init__(self) -> None:
        super().__init__()
        self._headers: dict[str, str] = {}

    # ── Abstract implementation ────────────────────────────────────────────── #

    @property
    def platform_name(self) -> str:
        return "flipkart"

    def can_handle(self, url: str) -> bool:
        """
        True for any Flipkart URL — both standard and deep link domains.
        Handles:
            https://www.flipkart.com/...
            https://flipkart.com/...
            https://dl.flipkart.com/dl/...   (canonical form stored in DB since v2.9)
        """
        return "flipkart.com" in url

    def extract_product_id(self, url: str) -> Optional[str]:
        """
        Extract Flipkart PID from URL. Pure string parsing — no network call.

        Priority:
          1. ?pid=BCHDAH9QHFTH5GRZ  — query param (most reliable; present on
             search result URLs and product pages with variant selectors)
          2. /p/itm62f0f8b3c0bfb    — path segment (canonical product URLs)

        Returns None if neither is found (e.g. category pages, wishlist links).
        """
        parsed = urlparse(url)

        # 1. Query param (highest priority — explicit PID in URL)
        params = parse_qs(parsed.query)
        if "pid" in params and params["pid"]:
            pid = params["pid"][0].strip()
            if pid:
                logger.info(
                    f"[AFFILIATE][flipkart] extracted pid={pid} from query param"
                )
                return pid

        # 2. Path segment — /p/itm{id}
        match = _PID_FROM_PATH.search(parsed.path)
        if match:
            pid = match.group(1)
            logger.info(
                f"[AFFILIATE][flipkart] extracted pid={pid} from path"
            )
            return pid

        logger.info(
            f"[AFFILIATE][flipkart] no PID found in url={url}"
        )
        return None

    def _authenticate(self) -> None:
        """
        Validate Flipkart affiliate credentials from config and build request headers.

        Flipkart's affiliate API uses static headers — there is no token exchange
        or session to create. This method:
          1. Reads flipkart_affiliate_id and flipkart_affiliate_token from Settings.
          2. Raises AffiliateAuthError if either is missing/empty.
          3. Stores the headers dict in self._headers for use by _fetch().

        Called by fetch() once at startup and again by _call_with_retry() on
        AffiliateTimeoutError / AffiliateAuthError (re-auth path).
        """
        affiliate_id = getattr(settings, "flipkart_affiliate_id", "").strip()
        affiliate_token = getattr(settings, "flipkart_affiliate_token", "").strip()

        if not affiliate_id:
            raise AffiliateAuthError(
                "FLIPKART_AFFILIATE_ID is not configured — "
                "set it in Railway Variables and .env"
            )
        if not affiliate_token:
            raise AffiliateAuthError(
                "FLIPKART_AFFILIATE_TOKEN is not configured — "
                "add it to Railway Variables and .env"
            )

        self._headers = {
            "Fk-Affiliate-Id": affiliate_id,
            "Fk-Affiliate-Token": affiliate_token,
        }
        logger.info(
            f"[AFFILIATE][flipkart] credentials loaded — "
            f"affiliate_id={affiliate_id[:4]}***"
        )

    def _fetch(self, product_id: str) -> AffiliateResult:
        """
        GET /affiliate/1.0/product.json?query=<product_id>

        Makes one HTTP request to the Flipkart Affiliate API and parses the
        response into an AffiliateResult.

        Raises:
            AffiliateTimeoutError    — requests.Timeout
            AffiliateAuthError       — HTTP 401 or 403
            AffiliateRateLimitError  — HTTP 429
            AffiliateNotFoundError   — HTTP 404 or empty productInfoList
            AffiliateError           — any other non-200 status or parse failure
        """
        endpoint = f"{_API_BASE}{_PRODUCT_ENDPOINT}"
        params = {"id": product_id}    # FIX: Flipkart API requires 'id=', not 'query='

        logger.info(
            f"[AFFILIATE][flipkart] GET {endpoint} "
            f"id={product_id} timeout={_REQUEST_TIMEOUT_S}s"
        )

        try:
            resp = requests.get(
                endpoint,
                headers=self._headers,
                params=params,
                timeout=_REQUEST_TIMEOUT_S,
            )
        except requests.Timeout:
            raise AffiliateTimeoutError(
                f"Request timed out after {_REQUEST_TIMEOUT_S}s "
                f"for product_id={product_id}"
            )
        except requests.RequestException as e:
            # Network-level error (DNS failure, connection reset, etc.)
            raise AffiliateError(f"Network error for product_id={product_id}: {e}")

        logger.info(
            f"[AFFILIATE][flipkart] HTTP {resp.status_code} "
            f"product_id={product_id} "
            f"response_size={len(resp.content)} bytes"
        )

        # ── HTTP status handling ───────────────────────────────────────────── #
        if resp.status_code == 401 or resp.status_code == 403:
            raise AffiliateAuthError(
                f"HTTP {resp.status_code} — token rejected for product_id={product_id}"
            )
        if resp.status_code == 404:
            raise AffiliateNotFoundError(
                f"HTTP 404 — product_id={product_id} not found in Flipkart feed"
            )
        if resp.status_code == 429:
            raise AffiliateRateLimitError(
                f"HTTP 429 — rate limited for product_id={product_id}"
            )
        if resp.status_code != 200:
            raise AffiliateError(
                f"HTTP {resp.status_code} for product_id={product_id}: "
                f"{resp.text[:300]}"
            )

        # ── Parse JSON ────────────────────────────────────────────────────── #
        try:
            data = resp.json()
        except ValueError as e:
            raise AffiliateError(
                f"JSON parse failure for product_id={product_id}: {e}"
            )

        return self._parse(product_id, data)

    # ── Internal helpers ───────────────────────────────────────────────────── #

    def _parse(self, product_id: str, data: dict) -> AffiliateResult:
        """
        Parse the Flipkart Affiliate API v1.0 product response.

        Handles two response shapes:
          Shape A — direct product dict (single-product lookup response)
          Shape B — { productInfoList: [...] } (feed response format)

        Both shapes are normalised to the productBaseInfoV1 / productShippingInfoV1
        structure before field extraction.

        Raises:
            AffiliateNotFoundError — productInfoList is empty or base block absent
            AffiliateError         — selling price missing (unusable response)
        """
        # ── Normalise response shape ───────────────────────────────────────── #
        product_info: dict = data

        if "productInfoList" in data:
            items = data["productInfoList"]
            if not items:
                raise AffiliateNotFoundError(
                    f"productInfoList is empty for product_id={product_id}"
                )
            product_info = items[0]

        # v1.0 uses productBaseInfoV1; v0.1.0 uses productBaseInfo
        base: dict = (
            product_info.get("productBaseInfoV1")
            or product_info.get("productBaseInfo")
            or {}
        )
        if not base:
            raise AffiliateNotFoundError(
                f"No product base info block in response for product_id={product_id}"
            )

        # v0.1.0 wraps fields inside productAttributes; v1.0 puts them at root
        attrs: dict = base.get("productAttributes") or base

        # ── Price extraction helper ────────────────────────────────────────── #
        def _amount(field_name: str) -> Optional[Decimal]:
            """
            Extract an INR amount from a { amount: N, currency: 'INR' } block.
            Checks both attrs and base (handles schema version differences).
            Returns None if the field is absent or the amount is non-positive.
            """
            block = attrs.get(field_name) or base.get(field_name)
            if not block:
                return None
            raw = block.get("amount")
            if raw is None:
                return None
            try:
                val = Decimal(str(raw))
                return val if val > 0 else None
            except InvalidOperation:
                return None

        # ── Selling price (required) ───────────────────────────────────────── #
        # v1.0: flipkartSellingPrice   v0.1.0: sellingPrice
        selling_price = _amount("flipkartSellingPrice") or _amount("sellingPrice")
        if selling_price is None:
            raise AffiliateError(
                f"Selling price missing in response for product_id={product_id} "
                f"— response may be malformed"
            )

        # ── Image URL — prefer 400×400, fallback through resolutions ──────── #
        image_urls: dict = attrs.get("imageUrls") or {}
        image_url = (
            image_urls.get("400x400")
            or image_urls.get("200x200")
            or image_urls.get("800x800")
            or image_urls.get("unknown")  # original resolution
        )

        # ── Offers — raw strings ───────────────────────────────────────────── #
        raw_offers = attrs.get("offers") or []
        offers = [str(o) for o in raw_offers if o]

        # ── Discount percentage — stored as float or int in API ────────────── #
        discount_raw = attrs.get("discountPercentage")
        try:
            discount_pct = float(discount_raw) if discount_raw is not None else None
        except (TypeError, ValueError):
            discount_pct = None

        # ── Shipping info (seller name) ────────────────────────────────────── #
        shipping: dict = (
            product_info.get("productShippingInfoV1")
            or product_info.get("productShippingBaseInfo")
            or {}
        )
        seller_name: Optional[str] = shipping.get("sellerName")

        result = AffiliateResult(
            platform="flipkart",
            product_id=product_id,
            name=attrs.get("title") or base.get("title") or "",
            price=selling_price,
            mrp=_amount("maximumRetailPrice"),
            special_price=_amount("flipkartSpecialPrice"),
            discount_pct=discount_pct,
            availability=bool(attrs.get("inStock", True)),
            image_url=image_url,
            brand=attrs.get("productBrand") or base.get("productBrand"),
            offers=offers,
            seller_name=seller_name if seller_name else None,
            cod_available=attrs.get("codAvailable"),
        )

        logger.info(
            f"[AFFILIATE][flipkart] parsed — "
            f"product_id={product_id} "
            f"name={result.name[:50]!r} "
            f"price={result.price} "
            f"mrp={result.mrp} "
            f"discount={result.discount_pct}% "
            f"in_stock={result.availability} "
            f"offers={len(result.offers)}"
        )
        return result
