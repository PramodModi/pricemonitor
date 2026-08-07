import re
import urllib.request
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

from app.core.exceptions import InvalidURLError, UnsupportedPlatformError


_AMAZON_STRIP_PARAMS = {"ref", "ref_", "tag", "linkCode", "th", "psc", "smid", "dib", "dib_tag", "crid", "qid", "sprefix", "sr", "keywords"}
_FLIPKART_STRIP_PARAMS = {"affid", "affExtParam1", "affExtParam2", "otracker"}

_AMAZON_PRODUCT_PATTERNS = [
    re.compile(r"/dp/([A-Z0-9]{10})"),
    re.compile(r"/gp/product/([A-Z0-9]{10})"),
]
_FLIPKART_PRODUCT_PATTERNS = [
    re.compile(r"/p/([a-zA-Z0-9]+)"),
    re.compile(r"/dl/[^/]+/[^/]+/p/([a-zA-Z0-9]+)"),
]
_MYNTRA_PRODUCT_PATTERNS = [
    re.compile(r"/([0-9]+)/buy"),
]

SUPPORTED_DOMAINS = {
    "amazon.in": "amazon",
    "www.amazon.in": "amazon",
    "amzn.in": "amazon",
    "flipkart.com": "flipkart",
    "www.flipkart.com": "flipkart",
    "dl.flipkart.com": "flipkart",      # deep link domain
    "myntra.com": "myntra",
    "www.myntra.com": "myntra",
}

_KNOWN_UNSUPPORTED_DOMAINS = {
    "croma.com", "www.croma.com",
    "reliancedigital.in", "www.reliancedigital.in",
    "apple.com", "www.apple.com",
    "samsung.com", "www.samsung.com",
}

MAX_URL_LENGTH = 2048


@dataclass
class ValidatedURL:
    platform: str
    canonical_url: str
    marketplace_product_id: str


class URLValidator:
    def validate(self, raw_url: str) -> ValidatedURL:
        if not raw_url or len(raw_url) > MAX_URL_LENGTH:
            raise InvalidURLError(raw_url or "", "URL exceeds maximum length or is empty.")

        parsed = urlparse(raw_url.strip())
        if parsed.scheme not in ("http", "https"):
            raise InvalidURLError(raw_url, "URL must use http or https.")

        domain = parsed.netloc.lower()

        if domain in _KNOWN_UNSUPPORTED_DOMAINS:
            raise UnsupportedPlatformError(domain)

        if domain not in SUPPORTED_DOMAINS:
            raise InvalidURLError(raw_url, f"Domain '{domain}' is not supported.")

        platform = SUPPORTED_DOMAINS[domain]

        if domain == "amzn.in":
            return ValidatedURL(
                platform="amazon",
                canonical_url=raw_url.strip(),
                marketplace_product_id="",
            )

        # dl.flipkart.com/s/... — Flipkart mobile share short URL (Firebase Dynamic Link).
        # Resolve the HTTP redirect to the real product URL before scraping so that:
        #   1. Playwright navigates directly to the product page (avoids JS redirect timeout).
        #   2. The affiliate API can extract a product ID from the resolved URL.
        # Falls back to the original short URL if resolution fails.
        if domain == "dl.flipkart.com" and parsed.path.startswith("/s/"):
            resolved = self._resolve_short_url(raw_url.strip())
            if resolved != raw_url.strip():
                return self.validate(resolved)
            # Resolution failed — pass short URL through; Playwright will try
            return ValidatedURL(
                platform="flipkart",
                canonical_url=raw_url.strip(),
                marketplace_product_id="",
            )

        # Try normal pattern extraction first
        try:
            marketplace_product_id = self._extract_product_id(
                platform, parsed.path, raw_url
            )

            # For Amazon, always reconstruct a clean /dp/ URL
            if platform == "amazon" and marketplace_product_id:
                canonical_url = f"https://www.amazon.in/dp/{marketplace_product_id}"
            else:
                canonical_url = self._canonicalise(platform, parsed)

            return ValidatedURL(
                platform=platform,
                canonical_url=canonical_url,
                marketplace_product_id=marketplace_product_id,
            )
        except InvalidURLError:
            pass

        # If normal extraction failed, try to reconstruct a clean URL for Amazon
        if platform == "amazon":
            reconstructed = self._reconstruct_amazon_url(raw_url)
            if reconstructed:
                return ValidatedURL(
                    platform=platform,
                    canonical_url=reconstructed,
                    marketplace_product_id=reconstructed.split("/dp/")[1].split("/")[0],
                )

        raise InvalidURLError(
            raw_url,
            f"URL path does not match a known {platform} product page pattern.",
        )

    def _extract_product_id(self, platform: str, path: str, raw_url: str) -> str:
        if platform == "amazon":
            patterns = _AMAZON_PRODUCT_PATTERNS
        elif platform == "flipkart":
            patterns = _FLIPKART_PRODUCT_PATTERNS
        else:
            patterns = _MYNTRA_PRODUCT_PATTERNS
        for pattern in patterns:
            match = pattern.search(path)
            if match:
                return match.group(1)
        raise InvalidURLError(
            raw_url,
            f"URL path does not match a known {platform} product page pattern.",
        )

    def _canonicalise(self, platform: str, parsed) -> str:
        if platform == "flipkart":
            return self._canonicalise_flipkart(parsed)
        strip_params = _AMAZON_STRIP_PARAMS
        query_params = parse_qs(parsed.query, keep_blank_values=False)
        clean_params = {k: v for k, v in query_params.items() if k not in strip_params}
        clean_query = urlencode(clean_params, doseq=True)
        return urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            clean_query,
            "",
        ))

    def _canonicalise_flipkart(self, parsed) -> str:
        """
        Rewrite any Flipkart URL to the deep link format for app + web tracking.

        www.flipkart.com/a/b  →  https://dl.flipkart.com/dl/a/b
        dl.flipkart.com/dl/a/b  →  https://dl.flipkart.com/dl/a/b  (already correct)

        Affiliate params (affid, affExtParam1, affExtParam2, otracker) are stripped
        here — product_sync.py re-appends them with the configured affiliate ID.
        Legitimate params like pid= are preserved.
        """
        # Build the deep link path
        if parsed.netloc == "dl.flipkart.com":
            # Already a deep link — path is already /dl/...
            deep_path = parsed.path
        else:
            # www.flipkart.com — prepend /dl
            deep_path = "/dl" + parsed.path

        # Strip affiliate/tracker params, keep everything else (e.g. pid=)
        query_params = parse_qs(parsed.query, keep_blank_values=False)
        clean_params = {k: v for k, v in query_params.items() if k not in _FLIPKART_STRIP_PARAMS}
        clean_query = urlencode(clean_params, doseq=True)

        return urlunparse((
            "https",
            "dl.flipkart.com",
            deep_path,
            "",
            clean_query,
            "",
        ))

    def _resolve_short_url(self, url: str) -> str:
        """
        Follow HTTP redirects for a short URL and return the final destination URL.
        Used for Firebase Dynamic Links (dl.flipkart.com/s/...) which redirect to
        the real product page via HTTP 301/302 for non-mobile browsers.

        Returns the original URL unchanged on any network or timeout error so that
        the caller can fall back to passing the short URL directly to the browser.
        """
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.url
        except Exception:
            return url

    def _reconstruct_amazon_url(self, raw_url: str) -> Optional[str]:
        """
        Try to extract ASIN from any Amazon URL and reconstruct a clean /dp/ URL.
        Handles /gp/product/, /dp/, cart links, image links etc.
        """
        asin_patterns = [
            re.compile(r"/dp/([A-Z0-9]{10})"),
            re.compile(r"/gp/product/([A-Z0-9]{10})"),
            re.compile(r"/product/([A-Z0-9]{10})"),
            re.compile(r"[&?]asin=([A-Z0-9]{10})"),
            re.compile(r"/([A-Z0-9]{10})(?:[/?]|$)"),
        ]

        for pattern in asin_patterns:
            match = pattern.search(raw_url)
            if match:
                asin = match.group(1)
                return f"https://www.amazon.in/dp/{asin}"

        return None


url_validator = URLValidator()
