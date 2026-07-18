import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class RunFailureItem(BaseModel):
    product_id: uuid.UUID
    product_name: Optional[str] = None
    url: str
    scrape_status: str
    checked_at: datetime


class RunOut(BaseModel):
    run_id: uuid.UUID
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str
    products_total: Optional[int] = None
    products_scraped: Optional[int] = None
    products_failed: Optional[int] = None
    price_drops_found: Optional[int] = None
    emails_sent: Optional[int] = None
    failures: Optional[list[RunFailureItem]] = None

    model_config = {"from_attributes": True}


class RunListOut(BaseModel):
    total: int
    limit: int
    offset: int
    runs: list[RunOut]