import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.fastapi.schemas.product import (
    PreviewRequest, PreviewResponse, ProductOut,
    LiveData, CatalogData, PriceStats,
)
from app.services.url_validator import url_validator
from app.services.preview_cache import preview_cache, ProductSnapshot
from app.repositories.product_repo import ProductRepository
from app.core.exceptions import (
    InvalidURLError,
    UnsupportedPlatformError,
    ScrapeBotDetectedError,
    ScrapeError,
)
from app.scrapers.amazon import AmazonScraper
from app.scrapers.flipkart import FlipkartScraper
from app.utils.logging import get_logger

router = APIRouter(prefix="/products", tags=["products"])
logger = get_logger(__name__)

_amazon_scraper = AmazonScraper()
_flipkart_scraper = FlipkartScraper()


@router.post(
    "/preview",
    response_model=PreviewResponse,
    status_code=status.HTTP_200_OK,
)
def preview_product(
    body: PreviewRequest,
    db: Session = Depends(get_db),
) -> PreviewResponse:
    """
    Validate URL, scrape live data, look up existing catalog context,
    and return a preview token valid for 10 minutes.
    No database writes occur at this step.
    """
    # Step 1 — validate URL
    try:
        validated = url_validator.validate(body.url)
        logger.info(f"Validated URL — canonical={validated.canonical_url}, platform={validated.platform}, id={validated.marketplace_product_id}")
    except InvalidURLError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_URL",
                "message": "The submitted URL is not a supported product page.",
                "detail": exc.detail,
            },
        )
    except UnsupportedPlatformError as exc:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "UNSUPPORTED_PLATFORM",
                "message": f"{exc.domain} is not a supported platform.",
            },
        )

    # Step 2 — live scrape
    scraper = (
        _amazon_scraper
        if validated.platform == "amazon"
        else _flipkart_scraper
    )

    try:
        from playwright.sync_api import sync_playwright
        from playwright_stealth import Stealth

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                locale="en-IN",
                viewport={"width": 1280, "height": 800},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()
            Stealth().apply_stealth_sync(page)
            try:
                result = scraper.extract(page, validated.canonical_url)
            finally:
                context.close()
                browser.close()

    except ScrapeBotDetectedError:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "SCRAPE_BLOCKED",
                "message": "The marketplace blocked our request. Please try again.",
            },
        )
    except ScrapeError:
        raise HTTPException(
            status_code=502,
            detail={
                "code": "SCRAPE_FAILED",
                "message": "Could not extract product details. Please check the URL.",
            },
        )

    # Step 3 — assemble live_data
    marketplace_product_id = (
        result.marketplace_product_id or validated.marketplace_product_id
    )
    scraped_at = datetime.now(timezone.utc)

    live_data = LiveData(
        marketplace_product_id=marketplace_product_id,
        url=validated.canonical_url,
        platform=validated.platform,
        name=result.name or "",
        brand=result.brand,
        image_url=result.image_url,
        current_price=result.current_price,
        currency="INR",
        availability=result.availability,
        rating=result.rating,
        review_count=result.review_count,
        seller=result.seller,
        scraped_at=scraped_at,
    )

    # Step 4 — DB lookup (read-only)
    product_repo = ProductRepository(db)
    existing = product_repo.get_by_platform_and_marketplace_id(
        validated.platform, marketplace_product_id
    )

    catalog_data = None
    is_new_product = existing is None

    if existing:
        watcher_count = product_repo.get_watcher_count(existing.product_id)
        price_stats_raw = product_repo.get_price_stats(existing.product_id)

        price_change_indicator = None
        price_change_amount = None

        if existing.current_price is not None:
            if result.current_price < existing.current_price:
                price_change_indicator = "down"
                price_change_amount = existing.current_price - result.current_price
            elif result.current_price > existing.current_price:
                price_change_indicator = "up"
                price_change_amount = result.current_price - existing.current_price
            else:
                price_change_indicator = "unchanged"

        catalog_data = CatalogData(
            product_id=existing.product_id,
            last_tracked_price=existing.current_price,
            price_change_indicator=price_change_indicator,
            price_change_amount=price_change_amount,
            last_checked_at=existing.last_checked_at,
            watcher_count=watcher_count,
            price_stats=PriceStats(**price_stats_raw) if price_stats_raw else None,
        )

    # Step 5 — cache snapshot
    preview_id = uuid.uuid4()
    expires_at = preview_cache.make_expires_at()

    snapshot = ProductSnapshot(
        preview_id=preview_id,
        expires_at=expires_at,
        is_new_product=is_new_product,
        live_data=live_data.model_dump(),
        catalog_data=catalog_data.model_dump() if catalog_data else None,
    )
    preview_cache.store(snapshot)

    return PreviewResponse(
        preview_id=preview_id,
        expires_at=expires_at,
        is_new_product=is_new_product,
        live_data=live_data,
        catalog_data=catalog_data,
    )


@router.get(
    "/{product_id}",
    response_model=ProductOut,
)
def get_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ProductOut:
    """
    Retrieve full product details including watcher count and price stats.
    """
    product_repo = ProductRepository(db)
    product = product_repo.get_by_id(product_id)

    if product is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "PRODUCT_NOT_FOUND",
                "message": "Product not found.",
            },
        )

    watcher_count = product_repo.get_watcher_count(product_id)
    price_stats_raw = product_repo.get_price_stats(product_id)

    return ProductOut(
        **{
            c.name: getattr(product, c.name)
            for c in product.__table__.columns
        },
        watcher_count=watcher_count,
        price_stats=PriceStats(**price_stats_raw) if price_stats_raw else None,
    )