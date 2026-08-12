import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.fastapi.schemas.subscription import SubscribeRequest, SubscriptionOut, DeleteSubscriptionOut
from app.fastapi.schemas.product import ProductOut, PriceStats
from app.services.preview_cache import preview_cache
from app.services.product_sync import ProductSyncService
from app.services.subscription_service import SubscriptionService
from app.core.exceptions import (
    PreviewNotFoundError,
    SubscriptionNotFoundError,
    ProductNotFoundError,
)
from app.notifications.email_sender import EmailSender
from app.utils.logging import get_logger

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
logger = get_logger(__name__)


def _get_cross_portal_listings(db: Session, product_id: uuid.UUID) -> list[dict]:
    """
    Return other portal listings for the same canonical product. (v5.2)

    After a user subscribes, the frontend checks this to show Option B
    suggestion: "Also on Flipkart — ₹72,999 (last checked 3h ago)".

    Returns a list of dicts for other platforms where the same canonical
    product is tracked. Empty list when:
      - Product has no canonical_id (not identity-linked yet)
      - No other portal listings exist for this canonical
    """
    from sqlalchemy import select
    from app.core.models.product import Product

    # Get the subscribed product's canonical_id
    subscribed = db.get(Product, product_id)
    if subscribed is None or subscribed.canonical_id is None:
        return []

    # Find other portal listings for the same canonical
    rows = db.execute(
        select(
            Product.product_id,
            Product.platform,
            Product.current_price,
            Product.mrp,
            Product.url,
            Product.availability,
            Product.last_checked_at,
        ).where(
            Product.canonical_id == subscribed.canonical_id,
            Product.product_id != product_id,          # exclude the subscribed one
            Product.current_price.isnot(None),         # must have a known price
        ).order_by(Product.current_price.asc())        # cheapest first
    ).mappings().all()

    return [
        {
            "product_id":      str(row["product_id"]),
            "platform":        row["platform"],
            "current_price":   float(row["current_price"]),
            "mrp":             float(row["mrp"]) if row["mrp"] else None,
            "url":             row["url"],
            "availability":    row["availability"],
            "last_checked_at": row["last_checked_at"].isoformat() if row["last_checked_at"] else None,
        }
        for row in rows
    ]


@router.post(
    "",
    response_model=SubscriptionOut,
    status_code=status.HTTP_201_CREATED,
)
def subscribe(
    body: SubscribeRequest,
    db: Session = Depends(get_db),
) -> SubscriptionOut:
    """
    Consume a preview token and create (or confirm existing) subscription.
    """
    re_scraped = False

    try:
        snapshot = preview_cache.consume(str(body.preview_id))
        if snapshot.is_expired():
            raise PreviewNotFoundError(str(body.preview_id))
    except PreviewNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PREVIEW_NOT_FOUND",
                "message": "Preview not found or expired. Please search again.",
            },
        )

    sync_svc = ProductSyncService(db)
    result = sync_svc.sync(snapshot, str(body.email))
    db.commit()

    # Send confirmation email on new subscription only
    if result.is_new_subscription:
        try:
            sender = EmailSender()
            sender.send_subscription_confirmation(
                to_email=str(body.email),
                product_name=result.product.name or "Product",
                product_image_url=result.product.image_url,
                product_url=result.product.url,
                current_price=result.product.current_price,
                platform=result.product.platform,
            )
            logger.info(f"Confirmation email sent — to={str(body.email)}")
        except Exception as exc:
            logger.error(f"Confirmation email failed — error={str(exc)}")

    return SubscriptionOut(
        subscription_id=result.subscription_id,
        is_new_subscription=result.is_new_subscription,
        re_scraped=re_scraped,
        product=ProductOut.model_validate(result.product),
        cross_portal_listings=_get_cross_portal_listings(db, result.product.product_id),
    )


# ── Direct subscription (no preview / scrape required) ───────────────────────

class DirectSubscribeRequest(BaseModel):
    """Request body for POST /v1/subscriptions/direct."""
    product_id: uuid.UUID
    email: EmailStr


@router.post(
    "/direct",
    response_model=SubscriptionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Subscribe to an existing product without scraping",
)
def subscribe_direct(
    body: DirectSubscribeRequest,
    db: Session = Depends(get_db),
) -> SubscriptionOut:
    """
    Create (or silently confirm existing) subscription for a product already
    in the DB. No preview_id or live scrape required.

    Used by the /offers page "Monitor this" button — the product is already
    known so there is no need to re-scrape it.

    Raises:
        404 PRODUCT_NOT_FOUND: product_id does not exist in products table.
    """
    svc = SubscriptionService(db)

    try:
        result = svc.subscribe_direct(
            product_id=body.product_id,
            email=str(body.email),
        )
    except ProductNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PRODUCT_NOT_FOUND",
                "message": "Product not found.",
            },
        )

    db.commit()

    # Send confirmation email on new subscription only
    if result.is_new_subscription:
        try:
            sender = EmailSender()
            sender.send_subscription_confirmation(
                to_email=str(body.email),
                product_name=result.product.name or "Product",
                product_image_url=result.product.image_url,
                product_url=result.product.url,
                current_price=result.product.current_price,
                platform=result.product.platform,
            )
            logger.info(f"Confirmation email sent — to={str(body.email)}")
        except Exception as exc:
            logger.error(f"Confirmation email failed — error={str(exc)}")

    return SubscriptionOut(
        subscription_id=result.subscription_id,
        is_new_subscription=result.is_new_subscription,
        re_scraped=False,
        product=ProductOut.model_validate(result.product),
        cross_portal_listings=_get_cross_portal_listings(db, result.product.product_id),
    )


@router.delete(
    "/{subscription_id}",
    response_model=DeleteSubscriptionOut,
)
def unsubscribe(
    subscription_id: uuid.UUID,
    email: str = Query(..., description="Email address of the subscription owner."),
    db: Session = Depends(get_db),
) -> DeleteSubscriptionOut:
    """
    Remove a user's subscription. Deletes product if no subscribers remain.
    """
    svc = SubscriptionService(db)
    try:
        result = svc.unsubscribe(subscription_id, email)
        db.commit()
    except SubscriptionNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SUBSCRIPTION_NOT_FOUND",
                "message": "Subscription not found.",
            },
        )

    return DeleteSubscriptionOut(
        subscription_id=result.subscription_id,
        product_deleted=result.product_deleted,
        message=result.message,
    )
