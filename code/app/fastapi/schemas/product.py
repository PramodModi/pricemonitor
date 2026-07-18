import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


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
    live_data: LiveData
    catalog_data: Optional[CatalogData] = None


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

    model_config = {"from_attributes": True}