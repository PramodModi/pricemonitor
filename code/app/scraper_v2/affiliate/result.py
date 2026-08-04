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

    Typed fields (mrp, special_price, discount_pct, offers, seller_name,
    cod_available) are richer than what Playwright scraping provides.

    metadata holds all portal-specific, variable-shape enrichment data
    (description, images, category, subcategory, specs, features,
    sizes_available, material, fit, style_notes).
    engine.py merges this into products.metadata (JSONB) on write,
    preserving existing keys that the current scrape could not provide.
    """

    # ── Required ──────────────────────────────────────────────────────── #
    platform: str
    """
    Marketplace identifier: 'flipkart' | 'amazon' | 'myntra'.
    Matches the platform stored in products.platform.
    """

    product_id: str
    """
    Marketplace product identifier.
    Flipkart: PID (e.g. 'BCHDAH9QHFTH5GRZ')
    Amazon:   ASIN (e.g. 'B0CHX1W1XY')
    Myntra:   product ID from URL or JS state
    """

    name: str
    """Full product title as returned by the API or scraper."""

    price: Decimal
    """
    Selling price in INR (after standard discount, before bank/extra offers).
    Flipkart: flipkartSellingPrice.amount
    Amazon:   Offers.Listings[0].Price.Amount
    Myntra:   price from JS state or scraper
    """

    # ── Optional — richer than what scraping provides ─────────────────── #
    mrp: Optional[Decimal] = None
    """
    Maximum Retail Price (printed on the product).
    Flipkart: maximumRetailPrice.amount
    Amazon:   not reliably provided by PA-API; may be None.
    Myntra:   mrp from JS state when available.
    """

    special_price: Optional[Decimal] = None
    """
    Price after applying bank/card/extra offers on top of the selling price.
    Flipkart: flipkartSpecialPrice.amount
    Amazon/Myntra: not applicable; leave None.
    """

    discount_pct: Optional[float] = None
    """
    Discount percentage off MRP (e.g. 23.0 means 23% off).
    Flipkart: discountPercentage
    Amazon:   Offers.Listings[0].Price.Savings.Percentage
    Myntra:   discountDisplayLabel parsed or computed from mrp/price
    """

    availability: bool = True
    """
    True = in stock.
    Flipkart: inStock
    Amazon:   Offers.Listings[0].Availability.Type == 'Now'
    Myntra:   sizes array has at least one available size
    """

    image_url: Optional[str] = None
    """
    Primary product image URL.
    Flipkart: imageUrls['400x400'] or fallback resolutions.
    Amazon:   Images.Primary.Large.URL
    Myntra:   first image from JS state
    """

    brand: Optional[str] = None
    """
    Brand / manufacturer name.
    Flipkart: productBrand
    Amazon:   ItemInfo.ByLineInfo.Brand.DisplayValue
    Myntra:   brandName from JS state
    """

    offers: list[str] = field(default_factory=list)
    """
    Raw promotional offer strings (bank discounts, cashback, etc.).
    Flipkart: offers[] array
    Amazon/Myntra: not provided; leave empty.
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
    Amazon/Myntra: not provided; leave None.
    """

    metadata: dict = field(default_factory=dict)
    """
    Portal-specific enrichment data — variable shape, stored as JSONB.

    Unified schema (all portals write to the same keys where applicable):
      description     : str   — product description (all portals)
      images          : [str] — additional image URLs beyond image_url (all portals)
      category        : str   — top-level category (all portals)
      subcategory     : str   — subcategory / article type (all portals)
      specs           : dict  — key-value spec table (Flipkart, Amazon)
      features        : [str] — bullet point features (Flipkart, Amazon)
      sizes_available : [str] — available sizes (Myntra)
      material        : str   — fabric/material (Myntra)
      fit             : str   — fit type e.g. Regular, Slim (Myntra)
      style_notes     : str   — styling description (Myntra)

    Keys absent for a portal are simply missing — not null.
    engine.py merges on write: existing DB keys are preserved when the
    current scrape cannot provide them (API-first, scraper fills gaps).
    """
