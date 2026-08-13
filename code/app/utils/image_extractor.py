"""
image_extractor.py — extract product image URL from a product page.

File: app/utils/image_extractor.py

Used by web_search.py to enrich Tavily search results with real product images.
Tavily's own image search is unreliable — this fetches the actual product page
and extracts the canonical image using structured signals.

Extraction strategy (in priority order):
    1. og:image meta tag       — all major platforms (Amazon, Flipkart, Myntra)
    2. JSON-LD Product.image   — structured data, very reliable when present
    3. None                    — clean fallback, no broken images shown

Design:
    - Short timeout (3s) — enrichment only, never blocks the main response
    - Never raises — returns None on any error
    - Synchronous — called from a threadpool (FastAPI sync endpoint)
    - lxml parser for speed — falls back to html.parser if lxml unavailable
    - f-strings only for logging (DEV-006)

Usage:
    from app.utils.image_extractor import extract_product_image

    image_url = extract_product_image("https://www.amazon.in/dp/B08SF3MKQ6")
    # → "https://m.media-amazon.com/images/I/71something.jpg"
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Short timeout — this is enrichment only, never blocks the main flow
_TIMEOUT_S = 3

# Realistic browser headers — Amazon blocks requests without User-Agent
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}


def extract_product_image(url: str) -> Optional[str]:
    """
    Fetch a product page and extract the canonical product image URL.

    Tries extraction signals in priority order:
        1. og:image meta tag
        2. JSON-LD Product.image

    Args:
        url: Product page URL (Amazon, Flipkart, or Myntra).

    Returns:
        Absolute image URL string, or None if extraction fails.
        Never raises.
    """
    if not url or not url.startswith("http"):
        return None

    try:
        resp = requests.get(
            url,
            headers=_HEADERS,
            timeout=_TIMEOUT_S,
            allow_redirects=True,
        )
        if resp.status_code != 200:
            logger.debug(
                f"[IMAGE_EXTRACTOR] HTTP {resp.status_code} — url={url!r:.80}"
            )
            return None

        # Use lxml for speed — falls back to html.parser
        try:
            soup = BeautifulSoup(resp.text, "lxml")
        except Exception:
            soup = BeautifulSoup(resp.text, "html.parser")

        # ── Signal 1: og:image ────────────────────────────────────────────────
        # Present on Amazon, Flipkart, Myntra — most reliable signal.
        og = soup.find("meta", property="og:image")
        if og and og.get("content"):
            image_url = og["content"].strip()
            if image_url.startswith("http"):
                logger.debug(
                    f"[IMAGE_EXTRACTOR] og:image — url={url!r:.60} "
                    f"image={image_url!r:.80}"
                )
                return image_url

        # ── Signal 2: JSON-LD Product.image ──────────────────────────────────
        # Many product pages embed structured data with image URLs.
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                # Handle both single object and @graph array
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "Product":
                        image = item.get("image")
                        if isinstance(image, list) and image:
                            image = image[0]
                        if isinstance(image, str) and image.startswith("http"):
                            logger.debug(
                                f"[IMAGE_EXTRACTOR] JSON-LD — url={url!r:.60} "
                                f"image={image!r:.80}"
                            )
                            return image
            except Exception:
                continue

        logger.debug(f"[IMAGE_EXTRACTOR] no image found — url={url!r:.80}")
        return None

    except Exception as exc:
        logger.debug(
            f"[IMAGE_EXTRACTOR] error — url={url!r:.80} "
            f"error={type(exc).__name__}: {exc}"
        )
        return None


def extract_product_images_parallel(
    urls: list[str],
    max_workers: int = 3,
) -> dict[str, Optional[str]]:
    """
    Fetch images for multiple URLs in parallel using a thread pool.

    Args:
        urls:        List of product page URLs.
        max_workers: Max concurrent fetches (default 3).

    Returns:
        Dict mapping url → image_url (or None if extraction failed).
        Never raises.
    """
    if not urls:
        return {}

    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: dict[str, Optional[str]] = {}

    try:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_url = {
                executor.submit(extract_product_image, url): url
                for url in urls
            }
            for future in as_completed(future_to_url, timeout=_TIMEOUT_S + 1):
                url = future_to_url[future]
                try:
                    results[url] = future.result()
                except Exception:
                    results[url] = None
    except Exception as exc:
        logger.debug(f"[IMAGE_EXTRACTOR] parallel fetch error — {exc}")
        # Fill remaining with None
        for url in urls:
            if url not in results:
                results[url] = None

    return results
