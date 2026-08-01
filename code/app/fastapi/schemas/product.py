import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
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

    model_config = {"from_attributes": True}

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
