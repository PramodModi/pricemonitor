from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.fastapi.schemas.subscription import ItemsOut, ItemOut
from app.fastapi.schemas.product import ProductOut
from app.repositories.user_repo import UserRepository
from app.repositories.subscription_repo import SubscriptionRepository
from app.repositories.product_repo import ProductRepository

router = APIRouter(prefix="/items", tags=["items"])


@router.get("", response_model=ItemsOut)
def get_items(
    email: str = Query(..., description="User email address."),
    db: Session = Depends(get_db),
) -> ItemsOut:
    """
    Return all products tracked by the given email address.
    Returns empty list if email has no tracked products.
    """
    email = email.strip().lower()
    if "@" not in email:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_EMAIL",
                "message": "Please provide a valid email address.",
            },
        )

    user_repo = UserRepository(db)
    user = user_repo.get_by_email(email)

    if user is None:
        return ItemsOut(email=email, count=0, items=[])

    sub_repo = SubscriptionRepository(db)
    subscriptions = sub_repo.get_all_for_user(user.user_id)

    if not subscriptions:
        return ItemsOut(email=email, count=0, items=[])

    # ── Batch fetch all-time low + max prices — one query for all products ─
    # get_max_prices() returns MIN and MAX(price) from price_history per product.
    # Comparing against the all-time max correctly catches "price peaked
    # then dropped" — not just last-scrape fluctuations.
    product_ids = [sub.product.product_id for sub in subscriptions]
    product_repo = ProductRepository(db)
    price_stats = product_repo.get_max_prices(product_ids)

    # ── Build items with price_drop_pct + all_time_low/high ───────────────
    items = []
    for sub in subscriptions:
        product  = sub.product
        current  = product.current_price
        stats    = price_stats.get(product.product_id, {})
        min_price = stats.get("min_price")
        max_price = stats.get("max_price")

        price_drop_pct = None
        if (max_price is not None
                and current is not None
                and current < max_price
                and float(max_price - current) / float(max_price) >= 0.01):
            price_drop_pct = round(
                float((max_price - current) / max_price * 100), 1
            )

        items.append(ItemOut(
            subscription_id=sub.subscription_id,
            subscribed_at=sub.created_at,
            product=ProductOut.model_validate(sub.product),
            price_drop_pct=price_drop_pct,
            all_time_low=float(min_price) if min_price is not None else None,
            all_time_high=float(max_price) if max_price is not None else None,
        ))

    return ItemsOut(email=email, count=len(items), items=items)