# app/scraper_v2/affiliate/result.py
#
# Normalised product data returned by any affiliate API client.
# engine.py converts this to ScrapeResponse via _affiliate_result_to_scrape_response().
# Neither the base class nor any concrete client imports from scraper_v2.models —
# AffiliateResult is intentionally self-contained so the affiliate package can be
# tested and extracted independently.

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional


@dataclass
class AffiliateResult:
    """
    Normalised product data returned by any marketplace affiliate API client.

    Field mapping to ScrapeResponse (engine.py):
      name          → name
      price         → price
      availability  → availability
      image_url     → image_url
      brand         → brand
      product_id    → marketplace_product_id (stored in products table)
      platform      → platform

    Additional fields (mrp, special_price, discount_pct, offers, seller_name,
    cod_available) are richer than what Playwright scraping provides.
    engine.py passes them through to ScrapeResponse.extra if that field exists,
    or ignores them gracefully if not — callers should check before using.
    """

    # ── Required ──────────────────────────────────────────────────────── #
    platform: str
    """
    Marketplace identifier: 'flipkart' | 'amazon'.
    Matches the platform stored in products.platform.
    """

    product_id: str
    """
    Marketplace product identifier.
    Flipkart: PID (e.g. 'BCHDAH9QHFTH5GRZ')
    Amazon:   ASIN (e.g. 'B0CHX1W1XY')
    """

    name: str
    """Full product title as returned by the API."""

    price: Decimal
    """
    Selling price in INR (after standard discount, before bank/extra offers).
    Flipkart: flipkartSellingPrice.amount
    Amazon:   Offers.Listings[0].Price.Amount
    """

    # ── Optional — richer than what scraping provides ─────────────────── #
    mrp: Optional[Decimal] = None
    """
    Maximum Retail Price (printed on the product).
    Flipkart: maximumRetailPrice.amount
    Amazon:   not reliably provided by PA-API; may be None.
    """

    special_price: Optional[Decimal] = None
    """
    Price after applying bank/card/extra offers on top of the selling price.
    Flipkart: flipkartSpecialPrice.amount
    Amazon:   not applicable; leave None.
    """

    discount_pct: Optional[float] = None
    """
    Discount percentage off MRP (e.g. 23.0 means 23% off).
    Flipkart: discountPercentage
    Amazon:   Offers.Listings[0].Price.Savings.Percentage
    """

    availability: bool = True
    """
    True = in stock.
    Flipkart: inStock
    Amazon:   Offers.Listings[0].Availability.Type == 'Now'
    """

    image_url: Optional[str] = None
    """
    Product image URL (400×400 preferred).
    Flipkart: imageUrls['400x400'] or fallback resolutions.
    Amazon:   Images.Primary.Large.URL
    """

    brand: Optional[str] = None
    """
    Brand / manufacturer name.
    Flipkart: productBrand
    Amazon:   BrowseNodeInfo or ItemInfo.ByLineInfo.Brand.DisplayValue
    """

    offers: list[str] = field(default_factory=list)
    """
    Raw promotional offer strings (bank discounts, cashback, etc.).
    Stored as-is — structured parsing is deferred to a future phase.
    Flipkart: offers[] array
    Amazon:   not provided by PA-API in a simple form; leave empty.
    """

    seller_name: Optional[str] = None
    """
    Seller / fulfilled-by name.
    Flipkart: productShippingInfoV1.sellerName
    Amazon:   Offers.Listings[0].MerchantInfo.Name
    """

    cod_available: Optional[bool] = None
    """
    Cash-on-delivery available.
    Flipkart: codAvailable
    Amazon:   not provided; leave None.
    """
