import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr
from app.fastapi.schemas.product import ProductOut


class SubscribeRequest(BaseModel):
    preview_id: uuid.UUID
    email: EmailStr


class SubscriptionOut(BaseModel):
    subscription_id: uuid.UUID
    is_new_subscription: bool
    re_scraped: bool
    product: ProductOut


class ItemOut(BaseModel):
    subscription_id: uuid.UUID
    subscribed_at: datetime
    product: ProductOut
    # Price drop since the previous scrape — None when insufficient history
    # or when price has not dropped. Computed in GET /v1/items, not stored.
    price_drop_pct: Optional[float] = None

    model_config = {"from_attributes": True}


class ItemsOut(BaseModel):
    email: str
    count: int
    items: list[ItemOut]


class DeleteSubscriptionOut(BaseModel):
    subscription_id: uuid.UUID
    product_deleted: bool
    message: str