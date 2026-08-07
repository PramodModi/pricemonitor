import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from pydantic import BaseModel, field_validator


class PreviewRequest(BaseModel):
    url: str


class LiveData(BaseModel):
    marketplace_product_id: str
    url: str
    platform: str
    name: str
    brand: Optional[str] = None
    image_url: Optional[str] = None
    current_price: Decimal
    currency: str = "INR"
    availability: bool
    rating: Optional[Decimal] = None
    review_count: Optional[int] = None
    seller: Optional[str] = None
    scraped_at: datetime

    # ── Affiliate API enrichment (present only when source=affiliate_api) ─────
    # All default to None / empty — UI must check before rendering.
    # Populated for Flipkart via affiliate API; None for Amazon, Myntra,
    # and any browser-scraped result today. Will auto-show when future
    # platforms provide this data.
    mrp: Optional[Decimal] = None
    special_price: Optional[Decimal] = None
    discount_pct: Optional[float] = None
    offers: Optional[list[str]] = []

    # ── Extended metadata (JSONB) ──────────────────────────────────────────────
    # Portal-specific enrichment: description, images, category, subcategory,
    # specs, features, sizes_available, material, fit, style_notes.
    # Empty dict when not yet populated.
    product_metadata: dict = {}


class PriceStats(BaseModel):
    all_time_low: Decimal
    all_time_high: Decimal
    drop_count: int
    first_tracked_at: datetime


class CatalogData(BaseModel):
    product_id: uuid.UUID
    last_tracked_price: Optional[Decimal] = None
    price_change_indicator: Optional[str] = None
    price_change_amount: Optional[Decimal] = None
    last_checked_at: Optional[datetime] = None
    watcher_count: int
    price_stats: Optional[PriceStats] = None


class PreviewResponse(BaseModel):
    preview_id: uuid.UUID
    expires_at: datetime
    is_new_product: bool
    data_source: str          # "database" | "live_scrape"
    live_data: LiveData
    catalog_data: Optional[CatalogData] = None


class PricePoint(BaseModel):
    checked_at: datetime
    price: Decimal


class ProductOut(BaseModel):
    product_id: uuid.UUID
    marketplace_product_id: str
    url: str
    platform: str
    name: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    current_price: Optional[Decimal] = None
    currency: str
    availability: Optional[bool] = None
    rating: Optional[Decimal] = None
    review_count: Optional[int] = None
    seller: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    created_at: datetime
    watcher_count: Optional[int] = None
    price_stats: Optional[PriceStats] = None
    price_history: list[PricePoint] = []

    # ── Affiliate API enrichment (same as LiveData — None when not available) ─
    mrp: Optional[Decimal] = None
    special_price: Optional[Decimal] = None
    discount_pct: Optional[float] = None
    offers: Optional[list[str]] = []

    # ── Extended metadata (JSONB) ──────────────────────────────────────────────
    product_metadata: Optional[dict] = {}

    model_config = {"from_attributes": True}

    @field_validator("offers", mode="before")
    @classmethod
    def coerce_offers(cls, v: object) -> list:
        """Coerce NULL from DB (None) to empty list."""
        if v is None:
            return []
        return v

    @field_validator("product_metadata", mode="before")
    @classmethod
    def coerce_metadata(cls, v: object) -> dict:
        """Coerce NULL from DB (None) to empty dict."""
        if v is None:
            return {}
        return v

    @field_validator("price_history", mode="before")
    @classmethod
    def coerce_price_history(cls, v: object) -> list:
        """
        When ProductOut is built via model_validate(orm_product), Pydantic
        reads the ORM relationship and passes a list of PriceHistory ORM
        objects here. Convert each one to a dict so PricePoint can validate it.

        Rows with price=None (failed/blocked scrapes) are skipped — mirrors
        the scrape_status='success' and price IS NOT NULL filter in
        PriceHistoryRepository.get_for_product().

        Plain dicts and PricePoint instances are passed through unchanged —
        the get_product() handler path is unaffected.
        """
        if not v:
            return []
        result = []
        for item in v:
            if isinstance(item, dict):
                if item.get("price") is not None:
                    result.append(item)
            elif hasattr(item, "checked_at") and hasattr(item, "price"):
                # ORM object — skip rows with no price
                if item.price is not None:
                    result.append({"checked_at": item.checked_at, "price": item.price})
            else:
                result.append(item)
        return result


# ---------------------------------------------------------------------------
# Aliases and schemas for GET /v1/products/{id}/history endpoint
# ---------------------------------------------------------------------------

# PriceHistoryPoint is the same shape as PricePoint — alias so the router
# can import either name without changing the existing PricePoint class.
PriceHistoryPoint = PricePoint


class PriceHistoryOut(BaseModel):
    """Response body for GET /v1/products/{product_id}/history."""
    product_id: uuid.UUID
    period: str
    count: int
    history: List[PricePoint]


# ---------------------------------------------------------------------------
# Schemas for GET /v1/products (public product catalogue / offers page)
# ---------------------------------------------------------------------------

class ProductListItem(BaseModel):
    """
    Lean product DTO for the offers/catalogue listing page.
    Omits product_metadata and price_history — not needed for card display.
    Includes watcher_count and all-time low/high computed by the repository.
    """
    product_id: uuid.UUID
    name: Optional[str] = None
    image_url: Optional[str] = None
    url: str
    platform: str
    current_price: Optional[Decimal] = None
    mrp: Optional[Decimal] = None
    special_price: Optional[Decimal] = None
    discount_pct: Optional[float] = None
    availability: Optional[bool] = None
    rating: Optional[Decimal] = None
    review_count: Optional[int] = None
    last_checked_at: Optional[datetime] = None
    watcher_count: int = 0
    all_time_low: Optional[Decimal] = None
    all_time_high: Optional[Decimal] = None

    model_config = {"from_attributes": True}


class ProductListOut(BaseModel):
    """Response body for GET /v1/products."""
    total: int
    count: int
    platform: Optional[str] = None
    items: List[ProductListItem]
