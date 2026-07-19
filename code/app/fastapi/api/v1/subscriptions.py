import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.fastapi.schemas.subscription import SubscribeRequest, SubscriptionOut, DeleteSubscriptionOut
from app.fastapi.schemas.product import ProductOut
from app.services.preview_cache import preview_cache, ProductSnapshot
from app.services.product_sync import ProductSyncService
from app.services.subscription_service import SubscriptionService
from app.core.exceptions import (
    PreviewNotFoundError,
    SubscriptionNotFoundError,
)
from app.utils.logging import get_logger
from app.notifications.email_sender import EmailSender

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
logger = get_logger(__name__)


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

    return SubscriptionOut(
        subscription_id=result.subscription_id,
        is_new_subscription=result.is_new_subscription,
        re_scraped=re_scraped,
        product=ProductOut.model_validate(result.product),
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
@router.post("", response_model=SubscriptionOut, status_code=status.HTTP_201_CREATED)
def subscribe(body: SubscribeRequest, db: Session = Depends(get_db)) -> SubscriptionOut:
    ...
    sync_svc = ProductSyncService(db)
    result = sync_svc.sync(snapshot, str(body.email))
    db.commit()

    # Send confirmation email
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
        except Exception as exc:
            logger.error(f"Confirmation email failed — error={str(exc)}")
            # Don't fail the subscription if email fails

    return SubscriptionOut(
        subscription_id=result.subscription_id,
        is_new_subscription=result.is_new_subscription,
        re_scraped=re_scraped,
        product=ProductOut.model_validate(result.product),
    )