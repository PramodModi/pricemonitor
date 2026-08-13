"""
web_search.py — Tavily Search API wrapper for scrape failure fallback.

File: app/services/web_search.py

Used by POST /v1/products/search-by-name when the user selects Amazon or Myntra
and the product is not found in our DB. Flipkart uses the Affiliate Search API.

Design:
  - Searches amazon.in or myntra.com for the product name via Tavily
  - Fetches up to 10 raw results, re-ranks by query match score
  - Re-ranking uses search_scorer.score_candidate() — same signals as Flipkart
  - Top 3 results enriched with real product images via og:image / JSON-LD extraction
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

from app.utils.search_scorer import rank_candidates, query_title_similarity


# Platform-specific image domain whitelist
_PLATFORM_IMAGE_DOMAINS = {
    "myntra":   "assets.myntassets.com",
    "amazon":   "m.media-amazon.com",
    "flipkart": "rukminim",
}
from app.utils.image_extractor import extract_product_images_parallel

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

        # Truncate to first 8 words — long queries cause Tavily to return
        # off-domain results and irrelevant pages.
        # e.g. "Boat Wanderer Smart Kids Watch 2-Way Video Phone Call GPS Tracker..."
        #   →  "Boat Wanderer Smart Kids Watch 2-Way Video Phone"
        truncated_name = ' '.join(product_name.strip().split()[:8])

        # For Myntra, append "buy" to prefer individual product pages
        suffix = " buy" if platform == "myntra" else ""
        query = f"{truncated_name}{suffix} site:{site}" 

        logger.info(
            f"[WEB_SEARCH] Tavily search — "
            f"platform={platform} "
            f"query={query!r:.80} "
            f"limit={limit}"
        )

        # ── Fetch with retry — up to 3 attempts with increasing result count ──
        # Retry condition: query-title similarity of top result < 0.7
        # This catches cases where Tavily returns wrong-category results.
        from tavily import TavilyClient

        _MAX_RESULTS_BY_ATTEMPT = [10, 15, 20]
        response = None
        best_response = None
        best_sim = 0.0

        for attempt, max_results in enumerate(_MAX_RESULTS_BY_ATTEMPT, 1):
            try:
                client = TavilyClient(api_key=self._api_key)
                response = client.search(
                    query=query,
                    max_results=max_results,
                    search_depth="basic",
                    include_domains=[site],
                    include_images=True,
                )
            except Exception as exc:
                logger.warning(
                    f"[WEB_SEARCH] Tavily error attempt={attempt} — "
                    f"platform={platform} error={type(exc).__name__}: {exc}"
                )
                break

            raw_results = response.get("results") or []
            if not raw_results:
                break

            # Check query-title similarity of top result
            top_title = raw_results[0].get("title", "") if raw_results else ""
            top_sim = query_title_similarity(product_name, top_title)
            logger.info(
                f"[WEB_SEARCH] attempt={attempt} max_results={max_results} "
                f"got={len(raw_results)} top_sim={top_sim:.3f} "
                f"top_title={top_title!r:.60} platform={platform}"
            )

            # Keep the best response across attempts
            if top_sim > best_sim:
                best_sim = top_sim
                best_response = response

            # Count domain-filtered results (what actually reaches the user)
            domain_count = sum(1 for r in raw_results if site in r.get("url", ""))
            if (top_sim >= 0.7 and domain_count >= limit) or attempt == len(_MAX_RESULTS_BY_ATTEMPT):
                break
            reasons = []
            if top_sim < 0.7:
                reasons.append(f"top_sim={top_sim:.3f} < 0.7")
            if domain_count < limit:
                reasons.append(f"domain_count={domain_count} < limit={limit}")
            logger.info(
                f"[WEB_SEARCH] retrying — {', '.join(reasons)}"
            )

        # Use best response found across all attempts (fallback to last)
        response = best_response or response

        if not response:
            return []

        raw_results = response.get("results") or []
        if not raw_results:
            logger.info(
                f"[WEB_SEARCH] no results — "
                f"platform={platform} query={product_name!r:.50}"
            )
            return []

        # Build candidate dicts — filter to correct domain only
        # Tavily's include_domains is not always strict; enforce here.
        raw_candidates = [
            {
                "name":        r.get("title", ""),
                "title":       r.get("title", ""),
                "url":         r.get("url", ""),
                "snippet":     r.get("content"),
                "image_url":   None,
                "_raw_images": r.get("images", []),
            }
            for r in raw_results
            if r.get("url") and site in r.get("url", "")
        ]

        # Re-rank by query match score
        ranked = rank_candidates(raw_candidates, product_name, limit)

        # ── Image assignment — positional with platform domain filter ─────────
        # Only use images from the correct platform domain.
        # cavaathleisure.com, shopify CDNs etc. are filtered out for Myntra.
        # Assigned positionally to ranked candidates after domain filtering.
        img_domain = _PLATFORM_IMAGE_DOMAINS.get(platform, "")
        platform_images = [
            img for img in (response.get("images") or [])
            if img and isinstance(img, str) and img.startswith("http")
            and img_domain in img
            and not any(noise in img for noise in [
                "sprite", "nav-sprite", "loading", ".gif", "grey-pixel",
                "personalization", "aax-", "impb?", "favicon"
            ])
        ]

        # Assign positionally
        for i, c in enumerate(ranked):
            if i < len(platform_images):
                c["image_url"] = platform_images[i]

        # Per-result image fallback for Amazon
        for c in ranked:
            if not c.get("image_url"):
                per_result_imgs = [
                    img for img in (c.get("_raw_images") or [])
                    if img and isinstance(img, str)
                    and "m.media-amazon.com/images/I/" in img
                ]
                if per_result_imgs:
                    c["image_url"] = per_result_imgs[0]

        results = [
            WebSearchResult(
                url=c["url"],
                title=c["name"],
                snippet=c.get("snippet"),
                image_url=c.get("image_url"),
            )
            for c in ranked
            if c.pop("_raw_images", None) is not None or True  # strip internal key
        ]

        images_found = sum(1 for c in ranked if c.get("image_url"))
        logger.info(
            f"[WEB_SEARCH] found {len(results)} results after re-ranking — "
            f"platform={platform} query={product_name!r:.50} "
            f"images={images_found}/{len(ranked)} "
            f"platform_images={len(platform_images)}"
        )
        # Debug: log each candidate's image_url so we can trace frontend
        for i, r in enumerate(results):
            logger.info(
                f"[WEB_SEARCH] candidate[{i}] image_url={r.image_url!r:.100}"
            )
        return results


# ── Module-level singleton ────────────────────────────────────────────────────
google_cse_client = TavilySearchClient()   # name kept for import compatibility
