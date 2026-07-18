from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.fastapi.schemas.subscription import ItemsOut, ItemOut
from app.fastapi.schemas.product import ProductOut
from app.repositories.user_repo import UserRepository
from app.repositories.subscription_repo import SubscriptionRepository

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

    items = [
        ItemOut(
            subscription_id=sub.subscription_id,
            subscribed_at=sub.created_at,
            product=ProductOut.model_validate(sub.product),
        )
        for sub in subscriptions
    ]

    return ItemsOut(email=email, count=len(items), items=items)