"""
URLResolver — resolves any product share URL to a canonical URL + product ID.

File: app/services/url_resolver.py

Runs BEFORE ScraperEngine and BEFORE the DB lookup in the preview endpoint.
Caller (products.py) does:

    from app.services.url_resolver import url_resolver
    resolved = url_resolver.resolve(raw_url, platform)
    # resolved.canonical_url  → clean desktop product URL
    # resolved.product_id     → ASIN / Flipkart PID / Myntra catalog ID (or None)
    # resolved.method         → how it was resolved (for logging)
    # resolved.confidence     → 0.0–1.0

Design principles:
  - Never raises. All errors caught internally. Falls back to the original
    URL so the existing engine cascade runs unchanged — additive only.
  - No Playwright, no browsers. Plain HTTP requests + regex only.
  - ScraperAPI used only when free resolution fails, and only for
    URL resolution (not scraping). Costs 1 credit max per resolution.
  - scraper_v2 is NOT imported or touched. URL resolution is the
    caller's responsibility, not the engine's.
  - Module-level singleton `url_resolver` mirrors the url_validator pattern.

Portal strategies:
  Amazon
    Step 1: regex ASIN from URL path          — no network, <1ms
    Step 2: HTTP redirect follow (amzn.in)    — 1 GET, ~200ms
    Step 3: ScraperAPI redirect               — paid fallback

  Flipkart
    Step 1: regex PID from URL query/path     — no network, <1ms
    Step 2: ScraperAPI HTML fetch             — Firebase Dynamic Links
            (dl.flipkart.com/s/ cannot be followed via plain HTTP —
             Firebase serves a JS-rendered page, not a 301/302 redirect)

  Myntra
    Step 1: regex catalog ID from URL path    — no network, <1ms
    Step 2: HTTP redirect follow (onelink.me) — AppsFlyer uses standard 301/302
    Step 3: ScraperAPI og:url extraction      — unknown URL shapes

Logger: f-strings only (DEV-006).
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, parse_qs, urlunparse, urlencode

logger = logging.getLogger(__name__)

# ── Regex patterns ────────────────────────────────────────────────────────────

# Amazon ASIN — 10-char uppercase alphanumeric
_ASIN_DP_RE      = re.compile(r"/dp/([A-Z0-9]{10})")
_ASIN_GP_RE      = re.compile(r"/gp/product/([A-Z0-9]{10})")
# Bare ASIN anywhere in URL — only accept if starts with B or is all digits
# (reduces false positives from other 10-char segments)
_ASIN_BARE_RE    = re.compile(r"(?<![A-Z0-9])([B][A-Z0-9]{9}|[0-9]{10})(?![A-Z0-9])")

# Flipkart PID — uppercase alphanumeric, 10–20 chars, in ?pid= query param
_FK_PID_QUERY_RE = re.compile(r"[?&]pid=([A-Z0-9]{10,20})")
# Flipkart itm... path segment — used by affiliate API as fallback PID
_FK_PID_PATH_RE  = re.compile(r"/p/(itm[a-zA-Z0-9]+)", re.IGNORECASE)

# Myntra catalog ID — 6–8 digit number in URL path
_MYNTRA_ID_RE    = re.compile(r"/(\d{6,8})(?:/buy)?(?:[?#]|$)")

# HTML extraction — canonical link and og:url
_CANONICAL_RE    = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
    re.IGNORECASE,
)
_CANONICAL_RE2   = re.compile(
    r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']canonical["\']',
    re.IGNORECASE,
)
_OG_URL_RE       = re.compile(
    r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# HTTP request headers — minimal browser-like, avoids 403 on HEAD/GET
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-IN,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# ScraperAPI timeouts — resolution only, not full scraping
_SCRAPERAPI_REDIRECT_TIMEOUT_S = 20
_SCRAPERAPI_HTML_TIMEOUT_S     = 30


@dataclass
class ResolvedURL:
    """
    Result of URL resolution. Always returned — never None.

    Fields:
        portal:        "amazon" | "flipkart" | "myntra"
        canonical_url: Clean desktop product URL. Equal to input URL when
                       resolution failed (passthrough).
        product_id:    ASIN / Flipkart PID / Myntra catalog ID.
                       None when resolution failed.
        method:        How resolution was achieved. One of:
                         "regex"               — ASIN/PID/ID from URL (no network)
                         "http_redirect"       — followed HTTP 301/302
                         "scraperapi_redirect" — ScraperAPI followed redirect
                         "scraperapi_html"     — ScraperAPI HTML + regex
                         "og_url"              — og:url meta tag from HTML
                         "passthrough"         — all steps failed, using original URL
        confidence:    0.0–1.0. Used for logging. Not enforced as a gate.
    """
    portal:        str
    canonical_url: str
    product_id:    Optional[str]
    method:        str
    confidence:    float


class URLResolver:
    """
    Resolves any product share URL to a canonical URL + product_id.

    Usage:
        resolved = url_resolver.resolve(raw_url, platform)

    The `platform` argument comes from url_validator.validate() which runs
    first — portal detection is already done, no need to repeat it here.

    All three portal methods follow the same pattern:
        Step 1: Pure regex — extract ID from URL string (no network call)
        Step 2: Free network resolution (HTTP redirect or similar)
        Step 3: ScraperAPI fallback (paid, last resort)
        Fallback: return original URL as passthrough

    scraper_v2 engine receives `canonical_url` from the resolved result.
    For Flipkart, `product_id` is passed as a hint to the affiliate API
    client via `engine.scrape(url, product_id_hint=resolved.product_id)`
    so the affiliate API never has to re-extract it from the URL.
    """

    # ── Public entry point ────────────────────────────────────────────────────

    def resolve(self, url: str, portal: str) -> ResolvedURL:
        """
        Main entry point. Never raises.

        Args:
            url:    Any URL for the given portal — short, deep link, mobile,
                    desktop, affiliate-tagged, or share URL.
            portal: "amazon" | "flipkart" | "myntra" — already validated
                    by url_validator.validate() before this is called.

        Returns:
            ResolvedURL. On any failure, method="passthrough" and
            canonical_url equals the original url input.
        """
        try:
            if portal == "amazon":
                return self._resolve_amazon(url)
            elif portal == "flipkart":
                return self._resolve_flipkart(url)
            elif portal == "myntra":
                return self._resolve_myntra(url)
        except Exception as exc:
            logger.warning(
                f"[RESOLVER] unexpected error — "
                f"portal={portal} "
                f"url={url!r:.100} "
                f"error={type(exc).__name__}: {exc}"
            )

        return self._passthrough(portal, url)

    # ── Amazon ────────────────────────────────────────────────────────────────

    def _resolve_amazon(self, url: str) -> ResolvedURL:
        # ── Step 1: ASIN already in URL (no network call) ─────────────────────
        asin = self._extract_asin(url)
        if asin:
            canonical = f"https://www.amazon.in/dp/{asin}"
            logger.info(
                f"[RESOLVER][amazon] regex — "
                f"asin={asin} "
                f"url={url!r:.80}"
            )
            return ResolvedURL(
                portal="amazon",
                canonical_url=canonical,
                product_id=asin,
                method="regex",
                confidence=0.99,
            )

        # ── Step 2: amzn.in short URL — follow HTTP redirect ──────────────────
        # amzn.in responds to standard HTTP GET with 301→amazon.in/dp/ASIN.
        # Unlike Flipkart's Firebase, this works from Railway datacenter IPs.
        if "amzn.in" in url:
            resolved = self._http_follow(url, timeout=8)
            if resolved:
                asin = self._extract_asin(resolved)
                if asin:
                    canonical = f"https://www.amazon.in/dp/{asin}"
                    logger.info(
                        f"[RESOLVER][amazon] http_redirect — "
                        f"asin={asin} "
                        f"short={url!r:.60} "
                        f"resolved={resolved!r:.100}"
                    )
                    return ResolvedURL(
                        portal="amazon",
                        canonical_url=canonical,
                        product_id=asin,
                        method="http_redirect",
                        confidence=0.98,
                    )

        # ── Step 3: ScraperAPI redirect follow ────────────────────────────────
        # Used when Railway IPs are blocked even by amzn.in redirect server
        # (uncommon but possible). Costs 1 ScraperAPI credit.
        resolved = self._scraperapi_resolve_redirect(url)
        if resolved:
            asin = self._extract_asin(resolved)
            if asin:
                canonical = f"https://www.amazon.in/dp/{asin}"
                logger.info(
                    f"[RESOLVER][amazon] scraperapi_redirect — "
                    f"asin={asin}"
                )
                return ResolvedURL(
                    portal="amazon",
                    canonical_url=canonical,
                    product_id=asin,
                    method="scraperapi_redirect",
                    confidence=0.96,
                )

        # ── Passthrough ───────────────────────────────────────────────────────
        # engine.scrape() receives the original URL. Browser attempt 1 will
        # follow the redirect and page.url will capture the real amazon.in/dp/ASIN
        # URL — the existing v4.8 page_url_out mechanism handles this.
        logger.info(
            f"[RESOLVER][amazon] passthrough — "
            f"all steps failed, engine will handle — "
            f"url={url!r:.100}"
        )
        return self._passthrough("amazon", url)

    # ── Flipkart ──────────────────────────────────────────────────────────────

    def _resolve_flipkart(self, url: str) -> ResolvedURL:
        # ── Step 1: PID already in URL (no network call) ─────────────────────
        pid = self._extract_flipkart_pid(url)
        if pid:
            # Strip affiliate params, keep pid= and other legitimate params
            clean_url = self._clean_flipkart_url(url)
            logger.info(
                f"[RESOLVER][flipkart] regex — "
                f"pid={pid} "
                f"url={url!r:.80}"
            )
            return ResolvedURL(
                portal="flipkart",
                canonical_url=clean_url,
                product_id=pid,
                method="regex",
                confidence=0.99,
            )

        # ── Step 2: Firebase Dynamic Link — ScraperAPI HTML fetch ────────────
        # dl.flipkart.com/s/ URLs are Firebase Dynamic Links. Firebase does NOT
        # respond to plain HTTP redirects from non-mobile user agents — it serves
        # a full HTML page with JS-based redirect. Plain requests.get() returns
        # an HTML page, not a 301, so _http_follow() cannot resolve these.
        #
        # Strategy: fetch the HTML via ScraperAPI (which renders JS), then:
        #   1. Extract pid= from og:url or canonical href in the HTML
        #   2. Extract pid= anywhere in the raw HTML via regex
        #
        # HTTP HEAD attempt was removed (v4.8 FIX — HEAD times out on Railway
        # because dl.flipkart.com blocks Railway IPs on HTTPS).
        if "dl.flipkart.com" in url or "flipkart.com" in url:
            html = self._scraperapi_fetch_html(url)
            if html:
                # Try og:url first — most reliable (Flipkart sets this correctly)
                og_url = self._extract_og_url(html)
                if og_url:
                    pid = self._extract_flipkart_pid(og_url)
                    if pid:
                        clean_url = self._clean_flipkart_url(og_url)
                        logger.info(
                            f"[RESOLVER][flipkart] scraperapi_html (og:url) — "
                            f"pid={pid} "
                            f"og_url={og_url!r:.100}"
                        )
                        return ResolvedURL(
                            portal="flipkart",
                            canonical_url=clean_url,
                            product_id=pid,
                            method="scraperapi_html",
                            confidence=0.97,
                        )

                # Try canonical link href
                canonical_href = self._extract_canonical_href(html)
                if canonical_href:
                    pid = self._extract_flipkart_pid(canonical_href)
                    if pid:
                        clean_url = self._clean_flipkart_url(canonical_href)
                        logger.info(
                            f"[RESOLVER][flipkart] scraperapi_html (canonical) — "
                            f"pid={pid}"
                        )
                        return ResolvedURL(
                            portal="flipkart",
                            canonical_url=clean_url,
                            product_id=pid,
                            method="scraperapi_html",
                            confidence=0.95,
                        )

                # Raw regex scan — catches pid= anywhere in the HTML body
                m = _FK_PID_QUERY_RE.search(html)
                if m:
                    pid = m.group(1)
                    logger.info(
                        f"[RESOLVER][flipkart] scraperapi_html (raw regex) — "
                        f"pid={pid}"
                    )
                    return ResolvedURL(
                        portal="flipkart",
                        canonical_url=url,
                        product_id=pid,
                        method="scraperapi_html",
                        confidence=0.90,
                    )

        logger.info(
            f"[RESOLVER][flipkart] passthrough — "
            f"all steps failed — "
            f"url={url!r:.100}"
        )
        return self._passthrough("flipkart", url)

    # ── Myntra ────────────────────────────────────────────────────────────────

    def _resolve_myntra(self, url: str) -> ResolvedURL:
        # ── Step 1: Catalog ID in URL path (no network call) ─────────────────
        catalog_id = self._extract_myntra_id(url)
        if catalog_id:
            canonical = self._build_myntra_canonical(url, catalog_id)
            logger.info(
                f"[RESOLVER][myntra] regex — "
                f"catalog_id={catalog_id} "
                f"url={url!r:.80}"
            )
            return ResolvedURL(
                portal="myntra",
                canonical_url=canonical,
                product_id=catalog_id,
                method="regex",
                confidence=0.99,
            )

        # ── Step 2: AppsFlyer / Branch.io deep link — HTTP redirect ──────────
        # AppsFlyer (onelink.me) and Branch.io (app.link, myntra.page.link)
        # both respond to standard HTTP GET with 301/302 to the real product
        # URL. No JS needed. Works from Railway IPs.
        is_deep_link = any(
            domain in url
            for domain in ("onelink.me", "app.link", "myntra.page.link", "go.myntra.com")
        )
        if is_deep_link:
            resolved = self._http_follow(url, timeout=8)
            if resolved:
                catalog_id = self._extract_myntra_id(resolved)
                if catalog_id:
                    canonical = self._build_myntra_canonical(resolved, catalog_id)
                    logger.info(
                        f"[RESOLVER][myntra] http_redirect — "
                        f"catalog_id={catalog_id} "
                        f"deep_link={url!r:.60}"
                    )
                    return ResolvedURL(
                        portal="myntra",
                        canonical_url=canonical,
                        product_id=catalog_id,
                        method="http_redirect",
                        confidence=0.97,
                    )

        # ── Step 3: og:url from ScraperAPI ───────────────────────────────────
        # For unknown Myntra URL shapes — Myntra sets og:url reliably.
        html = self._scraperapi_fetch_html(url)
        if html:
            og_url = self._extract_og_url(html)
            if og_url:
                catalog_id = self._extract_myntra_id(og_url)
                if catalog_id:
                    canonical = self._build_myntra_canonical(og_url, catalog_id)
                    logger.info(
                        f"[RESOLVER][myntra] og_url — "
                        f"catalog_id={catalog_id} "
                        f"og_url={og_url!r:.100}"
                    )
                    return ResolvedURL(
                        portal="myntra",
                        canonical_url=canonical,
                        product_id=catalog_id,
                        method="og_url",
                        confidence=0.92,
                    )

        logger.info(
            f"[RESOLVER][myntra] passthrough — "
            f"all steps failed — "
            f"url={url!r:.100}"
        )
        return self._passthrough("myntra", url)

    # ── ID extraction helpers ─────────────────────────────────────────────────

    def _extract_asin(self, url: str) -> Optional[str]:
        """Extract ASIN from any Amazon URL. Returns None when not found."""
        # Standard /dp/ and /gp/product/ patterns — most reliable
        for pattern in (_ASIN_DP_RE, _ASIN_GP_RE):
            m = pattern.search(url)
            if m:
                return m.group(1)

        # Bare ASIN — only in URL path, starts with B or all digits
        # Applied only to amazon.in domain to reduce false positives
        parsed = urlparse(url)
        if "amazon.in" in parsed.netloc:
            m = _ASIN_BARE_RE.search(parsed.path)
            if m:
                return m.group(1)

        return None

    def _extract_flipkart_pid(self, url: str) -> Optional[str]:
        """
        Extract Flipkart PID from URL.
        Primary:  ?pid= query param (works with affiliate API)
        Fallback: /p/itm... path segment (works for browser scraping only)
        """
        # Query param — most reliable, works with affiliate API
        m = _FK_PID_QUERY_RE.search(url)
        if m:
            pid = m.group(1)
            if re.match(r'^[A-Z0-9]{10,20}$', pid):
                return pid

        # Path segment — itm... format
        m = _FK_PID_PATH_RE.search(url)
        if m:
            return m.group(1)

        return None

    def _extract_myntra_id(self, url: str) -> Optional[str]:
        """Extract Myntra catalog ID (6-8 digit number) from URL path."""
        m = _MYNTRA_ID_RE.search(url)
        return m.group(1) if m else None

    # ── URL building helpers ──────────────────────────────────────────────────

    def _clean_flipkart_url(self, url: str) -> str:
        """
        Strip affiliate/tracking params from a Flipkart URL.
        Preserves pid= and other legitimate product params.
        Affiliate params are re-appended by _build_affiliated_url() in product_sync.py.
        """
        _STRIP = {"affid", "affExtParam1", "affExtParam2", "otracker",
                  "otracker1", "fm", "ssid", "ppid", "sk", "dclid", "gclid"}
        parsed = urlparse(url)
        params = {
            k: v for k, v in
            (p.split("=", 1) for p in parsed.query.split("&") if "=" in p)
            if k not in _STRIP
        }
        clean_query = urlencode(params)
        return urlunparse((
            parsed.scheme or "https",
            parsed.netloc,
            parsed.path,
            "",
            clean_query,
            "",
        ))

    def _build_myntra_canonical(self, url: str, catalog_id: str) -> str:
        """
        Build a clean Myntra canonical URL.
        Preserves the product slug path up to the catalog ID, appends /buy,
        and strips all query params (tracking noise).

        Example:
            Input:  https://www.myntra.com/shoes/nike/air-max/12345678/buy?utm_source=...
            Output: https://www.myntra.com/shoes/nike/air-max/12345678/buy
        """
        parsed = urlparse(url)
        path = parsed.path

        # Find catalog_id position in path and truncate cleanly
        if catalog_id in path:
            idx = path.index(catalog_id)
            clean_path = path[:idx + len(catalog_id)] + "/buy"
        else:
            clean_path = path.rstrip("/") + f"/{catalog_id}/buy"

        return f"https://www.myntra.com{clean_path}"

    # ── HTML extraction helpers ───────────────────────────────────────────────

    def _extract_og_url(self, html: str) -> Optional[str]:
        """Extract og:url content from raw HTML."""
        m = _OG_URL_RE.search(html)
        return m.group(1) if m else None

    def _extract_canonical_href(self, html: str) -> Optional[str]:
        """Extract <link rel="canonical" href="..."> from raw HTML."""
        for pattern in (_CANONICAL_RE, _CANONICAL_RE2):
            m = pattern.search(html)
            if m:
                return m.group(1)
        return None

    # ── Network helpers ───────────────────────────────────────────────────────

    def _http_follow(self, url: str, timeout: int = 8) -> Optional[str]:
        """
        Follow HTTP redirects and return the final URL.

        Works for:
          - amzn.in short URLs (standard 301/302 to amazon.in/dp/ASIN)
          - AppsFlyer onelink.me (standard 301/302 to myntra.com/...)

        Does NOT work for:
          - dl.flipkart.com/s/ Firebase Dynamic Links (JS-rendered, not 301/302)

        Uses GET (not HEAD) because some redirect servers reject HEAD requests
        or don't include Location in HEAD response headers.

        Returns the final URL string, or None on any error.
        Never raises.
        """
        try:
            import requests
            resp = requests.get(
                url,
                allow_redirects=True,
                timeout=timeout,
                headers=_HEADERS,
            )
            final = resp.url
            if final and final != url:
                logger.debug(
                    f"[RESOLVER] http_follow — "
                    f"hops={len(resp.history)} "
                    f"final={final!r:.100}"
                )
                return final
        except Exception as exc:
            logger.debug(
                f"[RESOLVER] http_follow failed — "
                f"url={url!r:.80} "
                f"error={type(exc).__name__}: {exc}"
            )
        return None

    def _scraperapi_resolve_redirect(self, url: str) -> Optional[str]:
        """
        Use ScraperAPI to follow a redirect and return the final URL.
        Costs 1 credit (no render=true — just redirect follow).

        Used for Amazon short URLs when Railway IPs are blocked even by
        the amzn.in redirect server (uncommon). Never raises.
        """
        api_key = self._get_scraperapi_key()
        if not api_key:
            return None

        try:
            import requests
            resp = requests.get(
                "http://api.scraperapi.com",
                params={
                    "api_key":      api_key,
                    "url":          url,
                    "country_code": "in",
                    # No render=true — redirect follow only, not full JS render
                },
                timeout=_SCRAPERAPI_REDIRECT_TIMEOUT_S,
            )
            # ScraperAPI returns the final URL in a response header
            final = resp.headers.get("X-Scraperapi-Resolved-Url") or resp.url
            if final and str(final) != url:
                return str(final)
        except Exception as exc:
            logger.debug(
                f"[RESOLVER] scraperapi_resolve_redirect failed — "
                f"error={type(exc).__name__}: {exc}"
            )
        return None

    def _scraperapi_fetch_html(self, url: str) -> Optional[str]:
        """
        Fetch rendered HTML via ScraperAPI.
        Used for Flipkart Firebase short URLs (JS rendering needed to
        get destination URL embedded in meta tags).

        Standard (not premium) — render=true gives JS rendering at 5 credits.
        Premium (10 credits) is only used by the engine for full product scraping.
        This resolver only needs meta tags, not full product data.

        Returns rendered HTML string, or None on any error. Never raises.
        """
        api_key = self._get_scraperapi_key()
        if not api_key:
            logger.debug(
                f"[RESOLVER] scraperapi_fetch_html skipped — "
                f"SCRAPER_API_KEY not configured"
            )
            return None

        try:
            import requests
            resp = requests.get(
                "http://api.scraperapi.com",
                params={
                    "api_key":      api_key,
                    "url":          url,
                    "render":       "true",
                    "country_code": "in",
                    # No premium=true — we only need meta tags, not full JS app
                },
                timeout=_SCRAPERAPI_HTML_TIMEOUT_S,
            )
            if resp.status_code == 200 and len(resp.text) > 500:
                logger.debug(
                    f"[RESOLVER] scraperapi_fetch_html success — "
                    f"url={url!r:.80} "
                    f"size={len(resp.text)}"
                )
                return resp.text
            logger.debug(
                f"[RESOLVER] scraperapi_fetch_html unexpected response — "
                f"status={resp.status_code} "
                f"size={len(resp.text)}"
            )
        except Exception as exc:
            logger.debug(
                f"[RESOLVER] scraperapi_fetch_html failed — "
                f"url={url!r:.80} "
                f"error={type(exc).__name__}: {exc}"
            )
        return None

    # ── Utility ───────────────────────────────────────────────────────────────

    def _get_scraperapi_key(self) -> str:
        """
        Read ScraperAPI key from app settings or environment.
        Same pattern as engine._scraperapi_key().
        Never raises — returns empty string when not configured.
        """
        try:
            from app.core.config import settings
            return getattr(settings, "scraper_api_key", "") or ""
        except Exception:
            pass
        import os
        return os.getenv("SCRAPER_API_KEY", "")

    def _passthrough(self, portal: str, url: str) -> ResolvedURL:
        """Return the original URL unchanged. Used when all resolution steps fail."""
        return ResolvedURL(
            portal=portal,
            canonical_url=url,
            product_id=None,
            method="passthrough",
            confidence=0.3,
        )


# ── Module-level singleton ────────────────────────────────────────────────────
# Same pattern as url_validator — import and use directly:
#   from app.services.url_resolver import url_resolver
url_resolver = URLResolver()
