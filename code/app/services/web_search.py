"""
web_search.py — Tavily Search API wrapper for scrape failure fallback.

File: app/services/web_search.py

Used by POST /v1/products/search-by-name when the user selects Amazon or Myntra
and the product is not found in our DB. Flipkart uses the Affiliate Search API.

Design:
  - Searches amazon.in or myntra.com for the product name via Tavily
  - Fetches up to 10 raw results, re-ranks by query match score
  - Re-ranking uses search_scorer.score_candidate() — same signals as Flipkart
    (model number match, brand match, token overlap)
  - Returns top `limit` candidates after re-ranking
  - Free tier: 1,000 queries/month — sufficient for failure-only use case
  - Never raises — returns empty list on any error
  - f-strings only for logging (DEV-006)

Setup:
  1. Sign up at https://tavily.com
  2. Copy API key from dashboard (starts with tvly-)
  3. Set env var:
       TAVILY_API_KEY=tvly-your_key_here

pip install tavily-python
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

from app.utils.search_scorer import rank_candidates

# Site restriction per platform
_PLATFORM_SITE = {
    "amazon":   "amazon.in",
    "flipkart": "flipkart.com",
    "myntra":   "myntra.com",
}


@dataclass
class WebSearchResult:
    """One candidate URL returned by Tavily search."""
    url: str
    title: str
    snippet: Optional[str] = None
    image_url: Optional[str] = None


class TavilySearchClient:
    """
    Thin wrapper around Tavily Search API.

    Usage:
        client = TavilySearchClient()
        results = client.search("Samsung Galaxy S24", platform="amazon", limit=5)
        for r in results:
            print(r.url, r.title)
    """

    def __init__(self) -> None:
        from app.core.config import settings
        self._api_key = settings.tavily_api_key.strip()

    @property
    def is_configured(self) -> bool:
        return bool(self._api_key and self._api_key.startswith("tvly-"))

    def search(
        self,
        product_name: str,
        platform: str,
        limit: int = 5,
    ) -> list[WebSearchResult]:
        """
        Search for a product on a specific platform via Tavily.

        Args:
            product_name: Product name typed by user (e.g. "Samsung Galaxy S24").
            platform:     "amazon" or "myntra".
            limit:        Max results to return (1–10).

        Returns:
            List of WebSearchResult with url, title, snippet.
            Empty list on any error or when not configured.
        """
        if not self.is_configured:
            logger.warning(
                f"[WEB_SEARCH] Tavily not configured — "
                f"set TAVILY_API_KEY env var"
            )
            return []

        site = _PLATFORM_SITE.get(platform)
        if not site:
            logger.warning(
                f"[WEB_SEARCH] unsupported platform={platform!r}"
            )
            return []

        query = f"{product_name.strip()} site:{site}"

        logger.info(
            f"[WEB_SEARCH] Tavily search — "
            f"platform={platform} "
            f"query={query!r:.80} "
            f"limit={limit}"
        )

        try:
            from tavily import TavilyClient
            client = TavilyClient(api_key=self._api_key)
            response = client.search(
                query=query,
                max_results=10,          # always fetch 10 — re-rank then trim
                search_depth="basic",
                include_domains=[site],
                include_images=True,
            )
        except Exception as exc:
            logger.warning(
                f"[WEB_SEARCH] Tavily error — "
                f"platform={platform} error={type(exc).__name__}: {exc}"
            )
            return []

        raw_results = response.get("results") or []
        if not raw_results:
            logger.info(
                f"[WEB_SEARCH] no results — "
                f"platform={platform} query={product_name!r:.50}"
            )
            return []

        # Build WebSearchResult objects — keep as dicts for re-ranking
        raw_candidates = [
            {
                "name":      r.get("title", ""),
                "title":     r.get("title", ""),   # score_candidate checks both
                "url":       r.get("url", ""),
                "snippet":   r.get("content"),
                "image_url": r.get("images", [None])[0] if r.get("images") else None,
            }
            for r in raw_results
            if r.get("url")
        ]

        # Re-rank by query match score — model number, brand, token overlap
        # Same scoring as Flipkart Affiliate results via search_scorer.
        ranked = rank_candidates(raw_candidates, product_name, limit)

        results = [
            WebSearchResult(
                url=c["url"],
                title=c["name"],
                snippet=c.get("snippet"),
                image_url=c.get("image_url"),
            )
            for c in ranked
        ]

        logger.info(
            f"[WEB_SEARCH] found {len(results)} results after re-ranking — "
            f"platform={platform} query={product_name!r:.50}"
        )
        return results


# ── Module-level singleton ────────────────────────────────────────────────────
google_cse_client = TavilySearchClient()   # name kept for import compatibility
