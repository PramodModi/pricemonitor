# app/scraper_v2/affiliate/__init__.py
#
# Package entry point for the affiliate API layer.
#
# AFFILIATE_CLIENTS is the ordered list of client instances consumed by
# ScraperEngine (attempt 0, before any Playwright browser is opened).
#
# Ordering rules:
#   - List clients from most capable / most likely to succeed first.
#   - ScraperEngine iterates the list and calls fetch() on the FIRST client
#     where can_handle(url) is True — so ordering only matters if two clients
#     could handle the same URL (which should not happen in practice).
#   - Stub clients (Amazon) are safe to include — _authenticate() raises
#     AffiliateAuthError immediately, fetch() returns None, engine falls through.
#
# To add a new marketplace:
#   1. Create app/scraper_v2/affiliate/myntra.py (subclass BaseAffiliateClient)
#   2. Import and add to AFFILIATE_CLIENTS below
#   3. Zero changes to engine.py, base.py, or any existing client

from app.scraper_v2.affiliate.base import BaseAffiliateClient
from app.scraper_v2.affiliate.flipkart import FlipkartAffiliateClient
from app.scraper_v2.affiliate.result import AffiliateResult

# AmazonAffiliateClient excluded until PA-API credentials are available.
# To activate: import AmazonAffiliateClient and add to the list below.
AFFILIATE_CLIENTS: list[BaseAffiliateClient] = [
    FlipkartAffiliateClient(),   # Active — requires FLIPKART_AFFILIATE_TOKEN
]

__all__ = [
    "AFFILIATE_CLIENTS",
    "AffiliateResult",
    "BaseAffiliateClient",
]
