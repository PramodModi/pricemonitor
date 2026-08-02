# app/scraper_v2/affiliate/amazon.py
#
# Amazon Product Advertising API (PA-API 5.0) client.
# Currently a STUB — fetch() is unreachable because _authenticate() always
# raises AffiliateAuthError when credentials are absent.
#
# When PA-API credentials arrive:
#   1. Add to app/core/config.py:
#        amazon_paapi_access_key: str = ""
#        amazon_paapi_secret_key: str = ""
#        amazon_paapi_partner_tag: str = ""   # affiliate tag / tracking ID
#   2. Add to Railway Variables + .env:
#        AMAZON_PAAPI_ACCESS_KEY=...
#        AMAZON_PAAPI_SECRET_KEY=...
#        AMAZON_PAAPI_PARTNER_TAG=...
#   3. Install paapi5-python-sdk or use requests with manual SigV4 signing.
#   4. Implement _authenticate() and _fetch() below.
#   5. Zero changes to base.py, __init__.py, or engine.py.
#
# PA-API 5.0 reference:
#   https://webservices.amazon.in/paapi5/documentation/get-items.html
#
# SigV4 signing:
#   Amazon PA-API uses AWS Signature Version 4. Every request must include
#   X-Amz-Date, Authorization, and X-Amz-Security-Token headers computed
#   from the Access Key, Secret Key, and request payload.
#   The official Python SDK (paapi5-python-sdk) handles this automatically.
#
# GetItems request body (JSON, POST):
#   {
#     "ItemIds": ["B0CHX1W1XY"],
#     "Resources": [
#       "Images.Primary.Large",
#       "ItemInfo.Title",
#       "ItemInfo.ByLineInfo",
#       "Offers.Listings.Price",
#       "Offers.Listings.Availability.Type",
#       "Offers.Listings.MerchantInfo"
#     ],
#     "PartnerTag": "<your_partner_tag>",
#     "PartnerType": "Associates",
#     "Marketplace": "www.amazon.in"
#   }
#
# Response path for price:
#   ItemsResult.Items[0].Offers.Listings[0].Price.Amount      (selling price)
#   ItemsResult.Items[0].Offers.Listings[0].Price.Savings.Percentage  (discount)
#   ItemsResult.Items[0].Offers.Listings[0].Availability.Type (in stock check)

import logging
import re
from typing import Optional

from app.scraper_v2.affiliate.base import BaseAffiliateClient
from app.scraper_v2.affiliate.exceptions import (
    AffiliateAuthError,
    AffiliateNotFoundError,
)
from app.scraper_v2.affiliate.result import AffiliateResult

logger = logging.getLogger(__name__)

# Matches /dp/{ASIN} in any Amazon URL.
# ASIN is always 10 uppercase alphanumeric characters.
_ASIN_FROM_PATH = re.compile(r"/dp/([A-Z0-9]{10})")


class AmazonAffiliateClient(BaseAffiliateClient):
    """
    Amazon PA-API 5.0 client — stub implementation.

    can_handle() and extract_product_id() are fully implemented.
    _authenticate() raises AffiliateAuthError until credentials are configured,
    which causes fetch() in BaseAffiliateClient to return None silently,
    making this client transparent (engine falls through to browser cascade).

    To activate:
        Implement _authenticate() and _fetch() as described in the module
        docstring above. No other files need to change.
    """

    @property
    def platform_name(self) -> str:
        return "amazon"

    def can_handle(self, url: str) -> bool:
        """
        True for standard Amazon India URLs and amzn.in short links.
        Handles:
            https://www.amazon.in/dp/{ASIN}
            https://amazon.in/dp/{ASIN}
            https://amzn.in/{short_code}   (resolved by URLValidator before storage)
        """
        return "amazon.in" in url or "amzn.in" in url

    def extract_product_id(self, url: str) -> Optional[str]:
        """
        Extract ASIN from /dp/{ASIN} in the URL path.
        Returns None for amzn.in short URLs (ASIN not in URL — needs resolution)
        and category/search pages.

        Note: URLValidator._reconstruct_amazon_url() normalises all Amazon URLs
        to https://www.amazon.in/dp/{ASIN} before they are stored in products.url,
        so the /dp/ pattern will match for all tracked products.
        """
        match = _ASIN_FROM_PATH.search(url)
        if match:
            asin = match.group(1)
            logger.info(
                f"[AFFILIATE][amazon] extracted asin={asin} from url"
            )
            return asin
        logger.info(
            f"[AFFILIATE][amazon] no ASIN found in url={url} — "
            f"may be short URL or non-product page"
        )
        return None

    # ── Stub implementations ────────────────────────────────────────────────── #

    def _authenticate(self) -> None:
        """
        STUB — raises AffiliateAuthError until PA-API credentials are configured.

        Implementation when credentials are available:
            from app.core.config import settings
            access_key = getattr(settings, 'amazon_paapi_access_key', '').strip()
            secret_key = getattr(settings, 'amazon_paapi_secret_key', '').strip()
            partner_tag = getattr(settings, 'amazon_paapi_partner_tag', '').strip()
            if not access_key or not secret_key or not partner_tag:
                raise AffiliateAuthError('Amazon PA-API credentials not configured')
            self._access_key = access_key
            self._secret_key = secret_key
            self._partner_tag = partner_tag
            # SigV4 signing is per-request — nothing to fetch here.
            logger.info('[AFFILIATE][amazon] PA-API credentials loaded')
        """
        raise AffiliateAuthError(
            "Amazon PA-API credentials not yet configured — "
            "set AMAZON_PAAPI_ACCESS_KEY, AMAZON_PAAPI_SECRET_KEY, "
            "AMAZON_PAAPI_PARTNER_TAG in Railway Variables"
        )

    def _fetch(self, product_id: str) -> AffiliateResult:
        """
        STUB — unreachable while _authenticate() raises AffiliateAuthError.

        Implementation when credentials are available:
            POST https://webservices.amazon.in/paapi5/getitems
            with SigV4-signed headers and JSON body shown in module docstring.
            Parse ItemsResult.Items[0].Offers.Listings[0].Price.Amount → price.
            Map fields to AffiliateResult and return.
        """
        raise AffiliateNotFoundError(
            f"Amazon PA-API stub — product_id={product_id} cannot be fetched "
            f"until credentials are configured"
        )
