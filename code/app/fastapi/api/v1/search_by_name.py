"""
search_by_name.py — scrape failure fallback endpoint.

File: app/fastapi/api/v1/search_by_name.py

POST /v1/products/search-by-name

Used when a URL scrape fails and the user types a product name instead.
Returns a list of product candidates from the appropriate affiliate/search API:

  Flipkart → Flipkart Affiliate Search API (structured, free, no quota)
  Amazon   → Google Custom Search API (site:amazon.in {name})
  Myntra   → Google Custom Search API (site:myntra.com {name})

The caller (Track page fallback UI) displays the candidates and lets the user
pick one. The selected URL is then passed to the existing preview/subscribe flow.

Wire into main.py:
    from app.fastapi.api.v1 import search_by_name
    app.include_router(search_by_name.router, prefix="/v1")
"""

import re
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.scraper_v2.affiliate.flipkart import FlipkartAffiliateClient
from app.services.web_search import google_cse_client
from app.utils.logging import get_logger

router = APIRouter(prefix="/products", tags=["products"])
logger = get_logger(__name__)

# Singleton affiliate client
_flipkart_client = FlipkartAffiliateClient()

# ASIN pattern — 10 alphanumeric chars after /dp/
_ASIN_RE = re.compile(r"/dp/([A-Z0-9]{10})", re.IGNORECASE)


def _amazon_image_url(url: str) -> Optional[str]:
    """Extract ASIN from Amazon URL and return product image URL."""
    match = _ASIN_RE.search(url)
    if not match:
        return None
    asin = match.group(1).upper()
    return f"https://images-na.ssl-images-amazon.com/images/P/{asin}.jpg"


def _is_product_url(url: str, platform: str) -> bool:
    """Filter out search listing pages — only keep individual product pages."""
    if platform == "amazon":
        return "/dp/" in url
    if platform == "flipkart":
        # Accept: /p/itm..., ?pid=..., or any /p/ product path from Tavily
        return (
            "/p/itm" in url.lower() or
            "pid=" in url or
            re.search(r"/[^/]+-[^/]+/p/", url) is not None  # slug/p/ pattern
        )
    if platform == "myntra":
        # Accept product pages (/123456/buy) and category listing pages
        # Reject only the homepage and fashion-store landing pages
        parsed_path = url.split("?")[0].rstrip("/")
        if parsed_path in ("https://www.myntra.com", "https://myntra.com"):
            return False
        if "myntra-fashion-store" in url:
            return False
        return True
    return True


# ── Request / Response schemas ────────────────────────────────────────────────

class SearchByNameRequest(BaseModel):
    name: str
    platform: str       # "amazon" | "flipkart" | "myntra"
    limit: int = 5


class ProductCandidate(BaseModel):
    """One product candidate returned by the search."""
    product_id: Optional[str] = None   # Flipkart PID or None for Amazon/Myntra
    name: str
    current_price: Optional[float] = None
    mrp: Optional[float] = None
    image_url: Optional[str] = None
    url: str                            # URL to pass to preview endpoint
    availability: Optional[bool] = None
    brand: Optional[str] = None
    platform: str


class SearchByNameResponse(BaseModel):
    query: str
    platform: str
    count: int
    candidates: list[ProductCandidate]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/search-by-name",
    response_model=SearchByNameResponse,
    status_code=status.HTTP_200_OK,
    summary="Search for products by name on a specific platform",
)
def search_by_name(body: SearchByNameRequest) -> SearchByNameResponse:
    """
    Search for product candidates by name on a specific platform.

    Used as a scrape failure fallback — when POST /v1/products/preview fails,
    the frontend shows a recovery UI where the user types the product name and
    selects a platform. This endpoint returns candidates to display.

    Flipkart: uses Flipkart Affiliate Search API — structured, free, no quota.
    Amazon/Myntra: uses Google Custom Search API — requires GOOGLE_CSE_API_KEY
                   and GOOGLE_CSE_ID env vars. Returns empty when not configured.

    The returned `url` for each candidate can be passed directly to
    POST /v1/products/preview to start the normal track flow.

    Args:
        name:     Product name to search for.
        platform: "amazon" | "flipkart" | "myntra"
        limit:    Max candidates to return (1–10). Default 5.

    Returns:
        SearchByNameResponse with list of ProductCandidate.
        Empty candidates list (not 404) when no results found.

    Raises:
        400: Unsupported platform or empty name.
    """
    name = body.name.strip()
    platform = body.platform.strip().lower()
    limit = max(1, min(body.limit, 10))

    if not name:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_NAME", "message": "Product name cannot be empty."},
        )

    if platform not in ("amazon", "flipkart", "myntra"):
        raise HTTPException(
            status_code=400,
            detail={
                "code": "UNSUPPORTED_PLATFORM",
                "message": "Platform must be amazon, flipkart, or myntra.",
            },
        )

    logger.info(
        f"[SEARCH_BY_NAME] query={name!r:.60} "
        f"platform={platform} limit={limit}"
    )

    candidates: list[ProductCandidate] = []

    # ── Flipkart: Affiliate Search API → Tavily fallback ─────────────────────
    if platform == "flipkart":
        try:
            raw = _flipkart_client.search_by_name(query=name, limit=limit)
            candidates = [
                ProductCandidate(
                    product_id=r.get("product_id"),
                    name=r.get("name", ""),
                    current_price=r.get("current_price"),
                    mrp=r.get("mrp"),
                    image_url=r.get("image_url"),
                    url=r.get("url", ""),
                    availability=r.get("availability"),
                    brand=r.get("brand"),
                    platform="flipkart",
                )
                for r in raw
                if r.get("url")
            ]
        except Exception as exc:
            logger.warning(
                f"[SEARCH_BY_NAME] Flipkart affiliate search failed — error={exc}"
            )

        # Flipkart affiliate returned nothing → fall back to Tavily
        if not candidates:
            logger.info(
                f"[SEARCH_BY_NAME] Flipkart affiliate empty — falling back to Tavily"
            )
            try:
                results = google_cse_client.search(
                    product_name=name,
                    platform="flipkart",
                    limit=limit + 3,
                )
                candidates = [
                    ProductCandidate(
                        product_id=None,
                        name=r.title,
                        current_price=None,
                        mrp=None,
                        image_url=r.image_url or None,
                        url=r.url,
                        availability=None,
                        brand=None,
                        platform="flipkart",
                    )
                    for r in results
                    if r.url and _is_product_url(r.url, "flipkart")
                ][:limit]
            except Exception as exc:
                logger.warning(
                    f"[SEARCH_BY_NAME] Flipkart Tavily fallback failed — error={exc}"
                )

    # ── Amazon / Myntra: Tavily Search API ───────────────────────────────────
    else:
        try:
            results = google_cse_client.search(
                product_name=name,
                platform=platform,
                limit=limit + 3,   # fetch extra to account for filtered URLs
            )
            # Debug: log each result URL and filter outcome
            for r in results:
                passes = r.url and _is_product_url(r.url, platform)
                logger.info(
                    f"[SEARCH_BY_NAME] {platform} filter={'PASS' if passes else 'FAIL'} "
                    f"url={r.url!r:.80}"
                )
            candidates = [
                ProductCandidate(
                    product_id=None,
                    name=r.title,
                    current_price=None,
                    mrp=None,
                    image_url=r.image_url,
                    url=r.url,
                    availability=None,
                    brand=None,
                    platform=platform,
                )
                for r in results
                if r.url and _is_product_url(r.url, platform)
            ][:limit]
        except Exception as exc:
            logger.warning(
                f"[SEARCH_BY_NAME] Tavily search failed — "
                f"platform={platform} error={exc}"
            )

    logger.info(
        f"[SEARCH_BY_NAME] returning {len(candidates)} candidates — "
        f"platform={platform} query={name!r:.50}"
    )

    return SearchByNameResponse(
        query=name,
        platform=platform,
        count=len(candidates),
        candidates=candidates,
    )
