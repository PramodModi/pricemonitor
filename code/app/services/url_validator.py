import re
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

SUPPORTED_DOMAINS = {
    "amazon.in": "amazon",
    "www.amazon.in": "amazon",
    "amzn.in": "amazon",
    "flipkart.com": "flipkart",
    "www.flipkart.com": "flipkart",
}

_KNOWN_UNSUPPORTED_DOMAINS = {
    "croma.com", "www.croma.com",
    "reliancedigital.in", "www.reliancedigital.in",
    "myntra.com", "www.myntra.com",
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
                    canonical_url=reconstructed,  # use clean /dp/ URL
                    marketplace_product_id=reconstructed.split("/dp/")[1].split("/")[0],
                )

        raise InvalidURLError(
            raw_url,
            f"URL path does not match a known {platform} product page pattern.",
        )

    def _extract_product_id(self, platform: str, path: str, raw_url: str) -> str:
        patterns = (
            _AMAZON_PRODUCT_PATTERNS if platform == "amazon" else _FLIPKART_PRODUCT_PATTERNS
        )
        for pattern in patterns:
            match = pattern.search(path)
            if match:
                return match.group(1)
        raise InvalidURLError(
            raw_url,
            f"URL path does not match a known {platform} product page pattern.",
        )

    def _canonicalise(self, platform: str, parsed) -> str:
        strip_params = (
            _AMAZON_STRIP_PARAMS if platform == "amazon" else _FLIPKART_STRIP_PARAMS
        )
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
    
    def _reconstruct_amazon_url(self, raw_url: str) -> Optional[str]:
        """
        Try to extract ASIN from any Amazon URL and reconstruct a clean /dp/ URL.
        Handles /gp/product/, /dp/, cart links, image links etc.
        """
        # Try all known ASIN patterns
        asin_patterns = [
            re.compile(r"/dp/([A-Z0-9]{10})"),
            re.compile(r"/gp/product/([A-Z0-9]{10})"),
            re.compile(r"/product/([A-Z0-9]{10})"),
            re.compile(r"[&?]asin=([A-Z0-9]{10})"),
            # ASIN as a standalone path segment
            re.compile(r"/([A-Z0-9]{10})(?:[/?]|$)"),
        ]

        for pattern in asin_patterns:
            match = pattern.search(raw_url)
            if match:
                asin = match.group(1)
                return f"https://www.amazon.in/dp/{asin}"

        return None


url_validator = URLValidator()