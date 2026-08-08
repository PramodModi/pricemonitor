"""
CategoryMapper — maps raw portal category/breadcrumb text to a unified
PricePing category slug.

File: app/scraper_v2/scrapers/category_mapper.py

Usage:
    from app.scraper_v2.scrapers.category_mapper import map_category

    slug = map_category("Mobiles & Accessories")   # → "mobiles"
    slug = map_category("Men's T-Shirts")           # → "fashion"
    slug = map_category(None)                       # → "other"

Unified categories:
    mobiles      Phones, tablets, accessories
    electronics  Laptops, TVs, audio, cameras, appliances
    fashion      Clothing, footwear, bags, watches, jewellery
    home         Furniture, kitchen, bedding, décor, tools
    beauty       Skincare, haircare, personal care, fragrances
    sports       Fitness, outdoor, cycling, sports gear
    books        Books, music, movies, stationery
    toys         Toys, baby products, games
    other        Anything that does not match the above

Design:
    - Keyword lookup on lowercased input — O(1) after lower()
    - Keywords ordered most-specific first within each category
    - Falls back to "other" when nothing matches
    - Never raises — safe to call from scraper (failure must not abort scrape)

Adding new keywords:
    1. Add the keyword string to the appropriate list in _KEYWORD_MAP below.
    2. No other changes needed.

Adding a new category:
    1. Add a new list entry to _KEYWORD_MAP with a new slug key.
    2. Update the VALID_CATEGORIES set below for validation.
    3. Update the frontend pill list in FilterBar.jsx.
"""

from __future__ import annotations

from typing import Optional

from app.scraper_v2.core.logging import get_logger

logger = get_logger(__name__)

# ── Valid category slugs ──────────────────────────────────────────────────────

VALID_CATEGORIES: frozenset[str] = frozenset({
    "mobiles",
    "electronics",
    "fashion",
    "home",
    "beauty",
    "sports",
    "books",
    "toys",
    "other",
})

# ── Keyword → category mapping ────────────────────────────────────────────────
# Each entry: (keyword_substring, category_slug)
# Checked in order — first match wins.
# All keywords are lowercased; input is lowercased before matching.

_RULES: list[tuple[str, str]] = [
    # ── Mobiles ───────────────────────────────────────────────────────────────
    ("mobile",          "mobiles"),
    ("smartphone",      "mobiles"),
    ("phone",           "mobiles"),
    ("tablet",          "mobiles"),
    ("iphone",          "mobiles"),
    ("android",         "mobiles"),
    ("feature phone",   "mobiles"),
    ("smartwatch",      "mobiles"),   # wearables closer to mobiles than electronics
    ("earphone",        "mobiles"),
    ("earbud",          "mobiles"),
    ("headphone",       "mobiles"),   # commonly in mobiles accessories

    # ── Electronics ───────────────────────────────────────────────────────────
    ("laptop",          "electronics"),
    ("computer",        "electronics"),
    ("desktop",         "electronics"),
    ("monitor",         "electronics"),
    ("television",      "electronics"),
    ("tv",              "electronics"),
    ("camera",          "electronics"),
    ("printer",         "electronics"),
    ("speaker",         "electronics"),
    ("audio",           "electronics"),
    ("home theatre",    "electronics"),
    ("home theater",    "electronics"),
    ("refrigerator",    "electronics"),
    ("washing machine", "electronics"),
    ("air conditioner", "electronics"),
    ("microwave",       "electronics"),
    ("geyser",          "electronics"),
    ("appliance",       "electronics"),
    ("electronic",      "electronics"),
    ("gaming",          "electronics"),
    ("console",         "electronics"),
    ("power bank",      "electronics"),
    ("charger",         "electronics"),
    ("cable",           "electronics"),

    # ── Fashion ───────────────────────────────────────────────────────────────
    ("men",             "fashion"),
    ("women",           "fashion"),
    ("clothing",        "fashion"),
    ("apparel",         "fashion"),
    ("fashion",         "fashion"),
    ("shirt",           "fashion"),
    ("t-shirt",         "fashion"),
    ("tshirt",          "fashion"),
    ("trouser",         "fashion"),
    ("jeans",           "fashion"),
    ("dress",           "fashion"),
    ("kurta",           "fashion"),
    ("saree",           "fashion"),
    ("lehenga",         "fashion"),
    ("footwear",        "fashion"),
    ("shoes",           "fashion"),
    ("sandal",          "fashion"),
    ("sneaker",         "fashion"),
    ("bag",             "fashion"),
    ("handbag",         "fashion"),
    ("wallet",          "fashion"),
    ("watch",           "fashion"),
    ("jewellery",       "fashion"),
    ("jewelry",         "fashion"),
    ("accessory",       "fashion"),
    ("accessories",     "fashion"),
    ("sunglasses",      "fashion"),
    ("luggage",         "fashion"),

    # ── Home & Kitchen ────────────────────────────────────────────────────────
    ("home",            "home"),
    ("kitchen",         "home"),
    ("furniture",       "home"),
    ("bedding",         "home"),
    ("mattress",        "home"),
    ("pillow",          "home"),
    ("curtain",         "home"),
    ("decor",           "home"),
    ("lamp",            "home"),
    ("lighting",        "home"),
    ("cookware",        "home"),
    ("utensil",         "home"),
    ("garden",          "home"),
    ("tool",            "home"),
    ("cleaning",        "home"),
    ("storage",         "home"),
    ("dining",          "home"),

    # ── Beauty & Personal Care ────────────────────────────────────────────────
    ("beauty",          "beauty"),
    ("skincare",        "beauty"),
    ("skin care",       "beauty"),
    ("haircare",        "beauty"),
    ("hair care",       "beauty"),
    ("makeup",          "beauty"),
    ("cosmetic",        "beauty"),
    ("fragrance",       "beauty"),
    ("perfume",         "beauty"),
    ("deodorant",       "beauty"),
    ("personal care",   "beauty"),
    ("grooming",        "beauty"),
    ("shampoo",         "beauty"),
    ("moisturiser",     "beauty"),
    ("moisturizer",     "beauty"),
    ("sunscreen",       "beauty"),

    # ── Sports & Fitness ──────────────────────────────────────────────────────
    ("sports",          "sports"),
    ("fitness",         "sports"),
    ("exercise",        "sports"),
    ("gym",             "sports"),
    ("yoga",            "sports"),
    ("cycling",         "sports"),
    ("running",         "sports"),
    ("outdoor",         "sports"),
    ("trekking",        "sports"),
    ("cricket",         "sports"),
    ("football",        "sports"),
    ("badminton",       "sports"),
    ("tennis",          "sports"),

    # ── Books ─────────────────────────────────────────────────────────────────
    ("book",            "books"),
    ("novel",           "books"),
    ("stationery",      "books"),
    ("music",           "books"),
    ("movie",           "books"),
    ("dvd",             "books"),
    ("blu-ray",         "books"),

    # ── Toys & Baby ───────────────────────────────────────────────────────────
    ("toy",             "toys"),
    ("baby",            "toys"),
    ("kids",            "toys"),
    ("children",        "toys"),
    ("infant",          "toys"),
    ("toddler",         "toys"),
    ("game",            "toys"),
    ("puzzle",          "toys"),
    ("doll",            "toys"),
]


def map_category(raw: Optional[str]) -> str:
    """
    Map a raw category string from the scraper to a unified PricePing slug.

    Args:
        raw: Raw category text from product_metadata["category"] or
             product_metadata["subcategory"]. May be None.

    Returns:
        A valid category slug from VALID_CATEGORIES. Always returns a
        non-None string — falls back to "other" when nothing matches.

    Examples:
        >>> map_category("Mobiles & Accessories")
        'mobiles'
        >>> map_category("Men's T-Shirts")
        'fashion'
        >>> map_category("Computers & Accessories")
        'electronics'
        >>> map_category(None)
        'other'
        >>> map_category("Random Uncategorised Thing")
        'other'
    """
    if not raw:
        return "other"

    needle = raw.lower().strip()

    for keyword, slug in _RULES:
        if keyword in needle:
            logger.debug(
                f"[CATEGORY] matched — raw={raw!r} keyword={keyword!r} slug={slug}"
            )
            return slug

    logger.debug(f"[CATEGORY] no match — raw={raw!r} → other")
    return "other"


def map_category_from_metadata(product_metadata: Optional[dict]) -> str:
    """
    Extract and map category from a product_metadata dict.

    Strategy: subcategory first, then category.
    Subcategory is more specific — e.g. Amazon puts phones under
    "Electronics" (category) but "Smartphones" (subcategory).
    Checking subcategory first correctly maps these to "mobiles".

    If subcategory produces "other" or is absent, falls back to category.

    Args:
        product_metadata: The product_metadata dict from ScrapeResponse
                          or the DB. May be None or empty.

    Returns:
        A valid category slug. Always "other" when nothing matches.
    """
    if not product_metadata:
        return "other"

    # Try subcategory first — more specific
    raw_sub = product_metadata.get("subcategory") or ""
    if raw_sub:
        slug = map_category(raw_sub)
        if slug != "other":
            return slug

    # Fall back to top-level category
    raw_category = product_metadata.get("category") or ""
    return map_category(raw_category)
