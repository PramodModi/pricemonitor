# app/scraper_v2/affiliate/flipkart.py
#
# Flipkart Affiliate API client — concrete implementation of BaseAffiliateClient.
#
# API used: GET /affiliate/1.0/product.json?id=<PID>
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
#     productBrand, offers, codAvailable, productDescription,
#     categoryPath, productAttributes
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
_SEARCH_ENDPOINT  = "/1.0/search.json"           # v5.2 — search by name

# Matches /p/itm{alphanumeric} in the URL path.
_PID_FROM_PATH = re.compile(r"/p/(itm[a-zA-Z0-9]+)", re.IGNORECASE)

_REQUEST_TIMEOUT_S: int = 10


# ── Search result re-ranking ─────────────────────────────────────────────── #
# Scoring logic lives in app/utils/search_scorer.py — shared with Tavily client
# so all platforms use identical ranking signals.
from app.utils.search_scorer import score_candidate as _score_candidate, rank_candidates


class FlipkartAffiliateClient(BaseAffiliateClient):
    """
    Flipkart Affiliate API client.

    Extracts all available product fields from the API response and populates
    both the typed AffiliateResult fields and the metadata dict for JSONB storage.

    Typed fields (products table columns):
        name, price, mrp, special_price, discount_pct, availability,
        image_url, brand, offers, seller_name, cod_available

    metadata dict keys (products.metadata JSONB):
        description, images, category, subcategory, specs, features
    """

    def __init__(self) -> None:
        super().__init__()
        self._headers: dict[str, str] = {}

    # ── Abstract implementation ────────────────────────────────────────────── #

    @property
    def platform_name(self) -> str:
        return "flipkart"

    def can_handle(self, url: str) -> bool:
        return "flipkart.com" in url

    def extract_product_id(self, url: str) -> Optional[str]:
        parsed = urlparse(url)

        params = parse_qs(parsed.query)
        if "pid" in params and params["pid"]:
            pid = params["pid"][0].strip()
            if pid:
                logger.info(
                    f"[AFFILIATE][flipkart] extracted pid={pid} from query param"
                )
                return pid

        match = _PID_FROM_PATH.search(parsed.path)
        if match:
            pid = match.group(1)
            logger.info(
                f"[AFFILIATE][flipkart] extracted pid={pid} from path"
            )
            return pid

        logger.info(f"[AFFILIATE][flipkart] no PID found in url={url}")
        return None

    def _authenticate(self) -> None:
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
        endpoint = f"{_API_BASE}{_PRODUCT_ENDPOINT}"
        params = {"id": product_id}

        logger.info(
            f"[AFFILIATE][flipkart] GET {endpoint} "
            f"id={product_id} timeout={_REQUEST_TIMEOUT_S}s"
        )

        try:
            import urllib.parse as _up
            # Flipkart API requires %20 for spaces — requests uses + by default.
            # Build query string manually with quote() instead of urlencode().
            query_string = '&'.join(
                f"{k}={_up.quote(str(v), safe='')}"
                for k, v in params.items()
            )
            full_url = f"{endpoint}?{query_string}"
            logger.info(
                f"[AFFILIATE][flipkart] request URL={full_url!r:.150}"
            )
            resp = requests.get(
                full_url,
                headers=self._headers,
                timeout=_REQUEST_TIMEOUT_S,
            )
        except requests.Timeout:
            raise AffiliateTimeoutError(
                f"Request timed out after {_REQUEST_TIMEOUT_S}s "
                f"for product_id={product_id}"
            )
        except requests.RequestException as e:
            raise AffiliateError(f"Network error for product_id={product_id}: {e}")

        logger.info(
            f"[AFFILIATE][flipkart] HTTP {resp.status_code} "
            f"product_id={product_id} "
            f"response_size={len(resp.content)} bytes"
        )

        if resp.status_code in (401, 403):
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

        try:
            data = resp.json()
        except ValueError as e:
            raise AffiliateError(
                f"JSON parse failure for product_id={product_id}: {e}"
            )

        return self._parse(product_id, data)

    def search_by_name(
        self,
        query: str,
        limit: int = 5,
    ) -> list[dict]:
        """
        Search Flipkart Affiliate API by product name. (v5.2)

        Used by POST /v1/products/search-by-name when the user selects Flipkart
        and the URL scrape failed. Returns structured product candidates without
        requiring a URL — the user picks one and the existing subscribe flow handles
        the rest.

        API: GET /affiliate/1.0/search.json?query={query}&resultCount=20

        Args:
            query: Product name typed by user (e.g. "Samsung Galaxy S24").
            limit: Max results to return (1–10). Default 5.

        Returns:
            List of candidate dicts with keys:
                product_id, name, current_price, mrp, image_url,
                url, availability, brand, category
            Empty list when no results or any error.

        Never raises — caller treats empty list as "no results found".
        """
        if not query or not query.strip():
            return []

        # Ensure credentials are loaded
        if not self._headers:
            try:
                self._authenticate()
            except Exception as exc:
                logger.warning(
                    f"[AFFILIATE][flipkart] search_by_name auth failed — "
                    f"error={exc}"
                )
                return []

        endpoint = f"{_API_BASE}{_SEARCH_ENDPOINT}"
        # Clean query — Flipkart Affiliate API returns HTTP 400 for special
        # characters like brackets, slashes, pipes. Strip them and collapse spaces.
        # e.g. "Zebronics (2800 lm / 2 Speaker)" → "Zebronics 2800 lm 2 Speaker"
        clean_query = re.sub(r'[^\w\s]', ' ', query).strip()
        clean_query = re.sub(r'\s+', ' ', clean_query)
        # Flipkart API rejects queries longer than ~80 chars with HTTP 400.
        # Truncate to first 8 words — covers brand + model + key descriptors.
        # Re-ranking handles relevance from these 8 words.
        # e.g. "ZEBRONICS Zeb Pixa Play 30 2800 lm 2 Speaker Wireless..." (160 chars)
        #   →  "ZEBRONICS Zeb Pixa Play 30 2800 lm 2"  (8 words, ~38 chars)
        clean_query = ' '.join(clean_query.split()[:8])

        params = {
            "query":       clean_query,
            "resultCount": 10,   # fetch 10 — Flipkart API max is 10
        }

        logger.info(
            f"[AFFILIATE][flipkart] search_by_name — "
            f"query={query!r:.60} limit={limit}"
        )
        logger.info(
            f"[AFFILIATE][flipkart] clean_query={clean_query!r:.60}"
        )

        try:
            import urllib.parse as _up
            # Flipkart API requires %20 for spaces — requests uses + by default.
            # Build query string manually with quote() instead of urlencode().
            query_string = '&'.join(
                f"{k}={_up.quote(str(v), safe='')}"
                for k, v in params.items()
            )
            full_url = f"{endpoint}?{query_string}"
            logger.info(
                f"[AFFILIATE][flipkart] request URL={full_url!r:.150}"
            )
            resp = requests.get(
                full_url,
                headers=self._headers,
                timeout=_REQUEST_TIMEOUT_S,
            )
        except requests.Timeout:
            logger.warning(
                f"[AFFILIATE][flipkart] search_by_name timeout — "
                f"query={query!r:.50}"
            )
            return []
        except requests.RequestException as exc:
            logger.warning(
                f"[AFFILIATE][flipkart] search_by_name network error — "
                f"error={exc}"
            )
            return []

        if resp.status_code != 200:
            logger.warning(
                f"[AFFILIATE][flipkart] search_by_name HTTP {resp.status_code} — "
                f"query={query!r:.50} response={resp.text[:200]!r}"
            )
            return []

        try:
            data = resp.json()
        except ValueError as exc:
            logger.warning(
                f"[AFFILIATE][flipkart] search_by_name JSON error — {exc}"
            )
            return []

        # Response shape: { "products": [ { "productBaseInfoV1": {...}, ... }, ... ] }
        raw_products = data.get("products") or data.get("productInfoList") or []
        candidates = []

        # Parse all returned results (up to 20) — re-rank after, then trim to limit
        for item in raw_products[:20]:
            try:
                base = (
                    item.get("productBaseInfoV1")
                    or item.get("productBaseInfo")
                    or {}
                )
                attrs = base.get("productAttributes") or base

                # Price
                def _amt(field: str) -> Optional[Decimal]:
                    block = attrs.get(field) or base.get(field)
                    if not block:
                        return None
                    raw = block.get("amount")
                    if raw is None:
                        return None
                    try:
                        v = Decimal(str(raw))
                        return v if v > 0 else None
                    except InvalidOperation:
                        return None

                price = _amt("flipkartSellingPrice") or _amt("sellingPrice")
                if price is None:
                    continue  # skip — no price means we can't display it

                image_urls = attrs.get("imageUrls") or {}
                image_url = (
                    image_urls.get("400x400")
                    or image_urls.get("200x200")
                    or image_urls.get("unknown")
                )

                product_id = (
                    attrs.get("productId")
                    or base.get("productId")
                    or ""
                )
                title = attrs.get("title") or base.get("title") or ""

                # Build affiliate URL from product_id
                affiliated_url = (
                    f"https://www.flipkart.com/product/p/itm"
                    f"?pid={product_id}"
                    f"&affid={getattr(settings, 'flipkart_affiliate_id', '')}"
                ) if product_id else ""

                candidates.append({
                    "product_id":    product_id,
                    "name":          title,
                    "current_price": float(price),
                    "mrp":           float(_amt("maximumRetailPrice")) if _amt("maximumRetailPrice") else None,
                    "image_url":     image_url,
                    "url":           affiliated_url,
                    "availability":  bool(attrs.get("inStock", True)),
                    "brand":         attrs.get("productBrand") or base.get("productBrand"),
                    "platform":      "flipkart",
                })
            except Exception as exc:
                logger.warning(
                    f"[AFFILIATE][flipkart] search_by_name parse error — "
                    f"error={exc}"
                )
                continue

        # ── Re-rank by query match score, return top `limit` ────────────────
        # rank_candidates() scores, sorts, strips _score, and trims to limit.
        # Shared with Tavily client — identical signals across all platforms.
        if candidates:
            candidates = rank_candidates(candidates, query, limit)
            for c in candidates[:3]:
                logger.info(
                    f"[AFFILIATE][flipkart] ranked — "
                    f"name={c['name'][:60]!r}"
                )

        logger.info(
            f"[AFFILIATE][flipkart] search_by_name found {len(candidates)} candidates — "
            f"query={query!r:.50}"
        )
        return candidates

    # ── Internal helpers ───────────────────────────────────────────────────── #

    def _parse(self, product_id: str, data: dict) -> AffiliateResult:
        """
        Parse the Flipkart Affiliate API v1.0 product response.

        Extracts all available fields into typed AffiliateResult attributes
        and a metadata dict for JSONB storage.
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
        selling_price = _amount("flipkartSellingPrice") or _amount("sellingPrice")
        if selling_price is None:
            raise AffiliateError(
                f"Selling price missing in response for product_id={product_id}"
            )

        # ── Image URL — prefer 400×400, collect all for metadata ──────────── #
        image_urls: dict = attrs.get("imageUrls") or {}
        primary_image = (
            image_urls.get("400x400")
            or image_urls.get("200x200")
            or image_urls.get("800x800")
            or image_urls.get("unknown")
        )
        # Collect all distinct image URLs for metadata
        all_images = list(dict.fromkeys(
            v for v in image_urls.values() if v
        ))

        # ── Offers — raw strings ───────────────────────────────────────────── #
        raw_offers = attrs.get("offers") or []
        offers = [str(o) for o in raw_offers if o]

        # ── Discount percentage ────────────────────────────────────────────── #
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
        seller_name: Optional[str] = shipping.get("sellerName") or None

        # ── Category path ─────────────────────────────────────────────────── #
        # categoryPath is a breadcrumb string like
        # "Electronics>Appliances>Kitchen Appliances>Dish washers"
        # Note: separator is ">" (single), not ">>"
        category_path: str = attrs.get("categoryPath") or base.get("categoryPath") or ""
        category_parts = [p.strip() for p in category_path.split(">") if p.strip()]
        category    = category_parts[0] if len(category_parts) > 0 else None
        subcategory = category_parts[-1] if len(category_parts) > 1 else None

        # ── categorySpecificInfoV1 — specs and features ────────────────────── #
        # Real API response puts structured specs and key features here,
        # NOT in productBaseInfoV1.productAttributes (which only has size/color).
        cat_specific: dict = product_info.get("categorySpecificInfoV1") or {}

        # ── Features / key specs ───────────────────────────────────────────── #
        # keySpecs is a flat list of highlight strings
        # e.g. ["Capacity: 13 Place Settings", "Control: Button", ...]
        raw_key_specs = cat_specific.get("keySpecs") or []
        features = [str(h).strip() for h in raw_key_specs if h and str(h).strip()]

        # ── Product specs ──────────────────────────────────────────────────── #
        # specificationList is a list of group dicts:
        # [{"key": "General", "values": [{"key": "Color", "value": ["White"]}, ...]}, ...]
        specs: dict = {}
        spec_list = cat_specific.get("specificationList") or []
        for group in spec_list:
            if not isinstance(group, dict):
                continue
            for item in group.get("values") or []:
                if not isinstance(item, dict):
                    continue
                spec_key = item.get("key") or ""
                spec_val_list = item.get("value") or []
                if spec_key and spec_val_list:
                    spec_val = ", ".join(str(v) for v in spec_val_list if v)
                    if spec_val and len(spec_key.strip()) > 1 and "cancellation" not in spec_val.lower():
                        specs[spec_key] = spec_val

        # ── Description ───────────────────────────────────────────────────── #
        description_raw: str = (
            attrs.get("productDescription")
            or base.get("productDescription")
            or ""
        )
        # Strip basic HTML tags if present
        description = re.sub(r"<[^>]+>", " ", description_raw).strip()
        description = re.sub(r"\s+", " ", description) or None

        # ── Build metadata dict ────────────────────────────────────────────── #
        metadata: dict = {}
        if description:
            metadata["description"] = description
        if all_images:
            metadata["images"] = all_images
        if category:
            metadata["category"] = category
        if subcategory:
            metadata["subcategory"] = subcategory
        if specs:
            metadata["specs"] = specs
        if features:
            metadata["features"] = features

        result = AffiliateResult(
            platform="flipkart",
            product_id=product_id,
            name=attrs.get("title") or base.get("title") or "",
            price=selling_price,
            mrp=_amount("maximumRetailPrice"),
            special_price=_amount("flipkartSpecialPrice"),
            discount_pct=discount_pct,
            availability=bool(attrs.get("inStock", True)),
            image_url=primary_image,
            brand=attrs.get("productBrand") or base.get("productBrand"),
            offers=offers,
            seller_name=seller_name,
            cod_available=attrs.get("codAvailable"),
            metadata=metadata,
        )

        logger.info(
            f"[AFFILIATE][flipkart] parsed — "
            f"product_id={product_id} "
            f"name={result.name[:50]!r} "
            f"price={result.price} "
            f"mrp={result.mrp} "
            f"discount={result.discount_pct}% "
            f"in_stock={result.availability} "
            f"offers={len(result.offers)} "
            f"specs={len(specs)} "
            f"features={len(features)} "
            f"category={category!r}"
        )
        return result
