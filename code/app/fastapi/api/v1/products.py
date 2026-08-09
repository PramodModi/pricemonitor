import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.fastapi.schemas.product import (
    PreviewRequest, PreviewResponse, ProductOut,
    LiveData, CatalogData, PriceStats, PriceHistoryPoint, PriceHistoryOut,
    ProductListItem, ProductListOut,
)
from app.services.url_validator import url_validator
from app.services.preview_cache import preview_cache, ProductSnapshot
from app.services.product_sync import _build_affiliated_url
from app.repositories.product_repo import ProductRepository
from app.repositories.price_history_repo import PriceHistoryRepository
from app.core.exceptions import (
    InvalidURLError,
    UnsupportedPlatformError,
    ScrapeBotDetectedError,
    ScrapeError,
)

from app.scraper_v2.engine import ScraperEngine

from app.scrapers.amazon import AmazonScraper
from app.scrapers.flipkart import FlipkartScraper
from app.utils.logging import get_logger

router = APIRouter(prefix="/products", tags=["products"])
logger = get_logger(__name__)

_amazon_scraper = AmazonScraper()
_flipkart_scraper = FlipkartScraper()


def _background_scrape_and_store(
    product_id: uuid.UUID,
    url: str,
    platform: str,
) -> None:
    """
    Background task — runs after PATH A preview returns to the user.

    Scrapes the product URL, updates price + metadata + affiliate fields
    in the DB so the next 🔄 Refresh returns fresh data.

    Opens its own DB session (runs outside the request lifecycle).
    Silently swallows all errors — must never crash the server.
    """
    from app.core.database import SessionLocal

    logger.info(
        f"[BACKGROUND_SCRAPE] start — "
        f"product_id={product_id} platform={platform} url={url}"
    )
    try:
        with ScraperEngine() as engine:
            result = engine.scrape(url)
    except Exception as exc:
        logger.warning(
            f"[BACKGROUND_SCRAPE] scrape failed — "
            f"product_id={product_id} error={exc}"
        )
        return

    if not result.success:
        logger.warning(
            f"[BACKGROUND_SCRAPE] scrape unsuccessful — "
            f"product_id={product_id} "
            f"error_type={result.error_type}"
        )
        return

    db = SessionLocal()
    try:
        product_repo = ProductRepository(db)
        ph_repo = PriceHistoryRepository(db)

        product = product_repo.get_by_id(product_id)
        if product is None:
            logger.warning(
                f"[BACKGROUND_SCRAPE] product not found in DB — "
                f"product_id={product_id}"
            )
            return

        # Update price if changed
        new_price = result.current_price
        if new_price is not None and new_price != product.current_price:
            product_repo.update_current_price(product, new_price)

        # Update metadata
        product_repo.update_from_live_data(
            product,
            {
                "name":            result.name or product.name,
                "brand":           result.brand,
                "image_url":       result.image_url,
                "availability":    result.availability,
                "rating":          result.rating,
                "review_count":    result.review_count,
                "seller":          result.seller,
                "last_checked_at": datetime.now(timezone.utc),
            },
        )

        # Write affiliate enrichment when present
        affiliate_mrp           = getattr(result, "mrp", None)
        affiliate_special_price = getattr(result, "special_price", None)
        affiliate_discount_pct  = getattr(result, "discount_pct", None)
        affiliate_offers        = getattr(result, "offers", []) or []

        if any(v is not None for v in [affiliate_mrp, affiliate_special_price,
                                        affiliate_discount_pct]) or affiliate_offers:
            product_repo.update_affiliate_data(
                product,
                mrp=affiliate_mrp,
                special_price=affiliate_special_price,
                discount_pct=affiliate_discount_pct,
                offers=affiliate_offers,
            )

        # Write product_metadata — merge so existing richer data is preserved
        incoming_metadata = getattr(result, "product_metadata", None) or {}
        if incoming_metadata:
            merged = ScraperEngine.merge_metadata(
                existing=product.product_metadata,
                incoming=incoming_metadata,
            )
            product_repo.update_product_metadata(product, merged)

        # Write category
        incoming_category = getattr(result, "category", None)
        if incoming_category:
            product_repo.update_category(product, incoming_category)
            logger.info(
                f"[BACKGROUND_SCRAPE] category written — "
                f"product_id={product_id} category={incoming_category}"
            )

        # Write price history row
        ph_repo.insert(
            product_id=product_id,
            price=new_price,
            scrape_status="success",
            run_id=None,
        )

        db.commit()
        logger.info(
            f"[BACKGROUND_SCRAPE] done — "
            f"product_id={product_id} "
            f"price={new_price} "
            f"mrp={affiliate_mrp} "
            f"offers_count={len(affiliate_offers)}"
        )

    except Exception as exc:
        db.rollback()
        logger.warning(
            f"[BACKGROUND_SCRAPE] DB write failed — "
            f"product_id={product_id} error={exc}"
        )
    finally:
        db.close()


def _build_catalog_data(existing, product_repo: ProductRepository, live_price=None) -> CatalogData:
    """
    Build CatalogData from an existing Product ORM row.
    live_price is used to compute the price_change_indicator when provided
    (Path B — live scrape). For Path A (DB-first), live_price is None and
    the indicator is omitted.
    """
    watcher_count = product_repo.get_watcher_count(existing.product_id)
    price_stats_raw = product_repo.get_price_stats(existing.product_id)

    price_change_indicator = None
    price_change_amount = None

    if live_price is not None and existing.current_price is not None:
        if live_price < existing.current_price:
            price_change_indicator = "down"
            price_change_amount = existing.current_price - live_price
        elif live_price > existing.current_price:
            price_change_indicator = "up"
            price_change_amount = live_price - existing.current_price
        else:
            price_change_indicator = "unchanged"

    return CatalogData(
        product_id=existing.product_id,
        last_tracked_price=existing.current_price,
        price_change_indicator=price_change_indicator,
        price_change_amount=price_change_amount,
        last_checked_at=existing.last_checked_at,
        watcher_count=watcher_count,
        price_stats=PriceStats(**price_stats_raw) if price_stats_raw else None,
    )


@router.post(
    "/preview",
    response_model=PreviewResponse,
    status_code=status.HTTP_200_OK,
)
def preview_product(
    body: PreviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> PreviewResponse:
    """
    Validate URL and return a preview token valid for 10 minutes.

    PATH A — known product (URL already in catalog):
        Return DB data immediately. No scrape. data_source = "database".

    PATH B — new product (URL not in catalog):
        Run a live scrape, return scraped data. data_source = "live_scrape".
        Unchanged from pre-v2.8 behaviour.

    No database writes occur at this step.
    """
    # ── Step 1 — validate URL ─────────────────────────────────────────────────
    try:
        validated = url_validator.validate(body.url)
        logger.info(
            f"Validated URL — canonical={validated.canonical_url} "
            f"platform={validated.platform} "
            f"id={validated.marketplace_product_id}"
        )
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

    # ── Step 2 — DB lookup FIRST ──────────────────────────────────────────────
    product_repo = ProductRepository(db)
    existing = None
    if validated.marketplace_product_id:
        existing = product_repo.get_by_platform_and_marketplace_id(
            validated.platform,
            validated.marketplace_product_id,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # PATH A — known product: serve from DB immediately, no scrape
    # ═════════════════════════════════════════════════════════════════════════
    if existing is not None:
        logger.info(
            f"Preview PATH A (DB hit) — product_id={existing.product_id} "
            f"platform={existing.platform}"
        )

        live_data = LiveData(
            marketplace_product_id=existing.marketplace_product_id,
            url=existing.url,
            platform=existing.platform,
            name=existing.name or "",
            brand=existing.brand,
            image_url=existing.image_url,
            current_price=existing.current_price,
            currency=existing.currency or "INR",
            availability=existing.availability if existing.availability is not None else False,
            rating=existing.rating,
            review_count=existing.review_count,
            seller=existing.seller,
            scraped_at=existing.last_checked_at or datetime.now(timezone.utc),
            # Read affiliate enrichment from DB — None when not yet populated
            mrp=existing.mrp,
            special_price=existing.special_price,
            discount_pct=float(existing.discount_pct) if existing.discount_pct is not None else None,
            offers=existing.offers or [],
        )

        catalog_data = _build_catalog_data(existing, product_repo, live_price=None)

        preview_id = uuid.uuid4()
        expires_at = preview_cache.make_expires_at()

        snapshot = ProductSnapshot(
            preview_id=preview_id,
            expires_at=expires_at,
            is_new_product=False,
            live_data=live_data.model_dump(),
            catalog_data=catalog_data.model_dump() if catalog_data else None,
        )
        preview_cache.store(snapshot)

        # ── Trigger background scrape to refresh DB data ──────────────────────
        # PATH A returns instantly with DB data. The background task scrapes
        # the live URL and updates price + metadata + affiliate fields in DB.
        # When the user clicks 🔄 Refresh, get_product() reads the fresh data.
        background_tasks.add_task(
            _background_scrape_and_store,
            product_id=existing.product_id,
            url=existing.url,
            platform=existing.platform,
        )
        logger.info(
            f"[PREVIEW] PATH A — background scrape queued — "
            f"product_id={existing.product_id}"
        )

        return PreviewResponse(
            preview_id=preview_id,
            expires_at=expires_at,
            is_new_product=False,
            data_source="database",
            live_data=live_data,
            catalog_data=catalog_data,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # PATH B — new product: live scrape (unchanged from pre-v2.8)
    # ═════════════════════════════════════════════════════════════════════════
    logger.info(
        f"Preview PATH B (DB miss, live scrape) — url={validated.canonical_url} "
        f"platform={validated.platform}"
    )

    try:
        if settings.use_scraper_v2:
            with ScraperEngine() as engine:
                result = engine.scrape(validated.canonical_url)

            # Write diagnostic row — preview path
            try:
                from app.scraper_v2.diagnostics.repository import ScrapeDiagnosticRepository
                from app.scraper_v2.models.scrape_result import ScrapeFailureReason
                diag_repo = ScrapeDiagnosticRepository(db)
                if result.success:
                    diag_status = "success"
                elif result.error_type == ScrapeFailureReason.BOT_DETECTED:
                    diag_status = "blocked"
                elif result.error_type == ScrapeFailureReason.TIMEOUT:
                    diag_status = "timeout"
                else:
                    diag_status = "failed"
                diag_repo.insert(
                    scrape_job_id=uuid.uuid4(),
                    portal=validated.platform,
                    url=validated.canonical_url,
                    status=diag_status,
                    trigger="preview",
                    triggered_by=None,
                    extraction_method=result.extraction_method,
                    error_type=(
                        result.error_type.value
                        if hasattr(result.error_type, "value")
                        else result.error_type
                    ),
                    error_message=result.error_message,
                    layers_attempted=result.layers_attempted or None,
                    layers_failed=result.layers_failed or None,
                    navigation_ms=result.navigation_ms,
                    extraction_ms=result.extraction_ms,
                    total_duration_ms=result.total_duration_ms,
                )
                db.commit()
            except Exception as diag_exc:
                db.rollback()
                logger.warning(f"Failed to write preview diagnostic — error={str(diag_exc)}")

            if not result.success:
                logger.error(
                    f"Scrape failed — url={validated.canonical_url} "
                    f"error_type={result.error_type} "
                    f"error={result.error_message}"
                )
                # Semaphore queue timeout — another scrape was already in progress.
                # Return 503 so the frontend shows "try again" immediately instead
                # of waiting for the Axios 35s timeout to expire.
                from app.scraper_v2.models.scrape_result import ScrapeFailureReason
                if result.error_type == ScrapeFailureReason.TIMEOUT and (
                    result.error_message and "queue" in (result.error_message or "").lower()
                ):
                    raise HTTPException(
                        status_code=503,
                        detail={
                            "code": "SCRAPE_BUSY",
                            "message": "Another product is being fetched. Please try again in a moment.",
                        },
                    )
                raise HTTPException(
                    status_code=502,
                    detail={
                        "code": "SCRAPE_FAILED",
                        "message": "Could not extract product details. Please check the URL.",
                    },
                )

        else:
            # v1 path — original code untouched
            from playwright.sync_api import sync_playwright
            from playwright_stealth import Stealth
            scraper = (
                _amazon_scraper
                if validated.platform == "amazon"
                else _flipkart_scraper
            )
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

    except HTTPException:
        raise
    except ScrapeBotDetectedError as exc:
        logger.error(f"Bot detected — url={validated.canonical_url} error={str(exc)}")
        raise HTTPException(
            status_code=502,
            detail={
                "code": "BOT_DETECTED",
                "message": "Could not extract product details. Please check the URL.",
            },
        )
    except ScrapeError as exc:
        logger.error(f"Scrape failed — url={validated.canonical_url} error={str(exc)}")
        raise HTTPException(
            status_code=502,
            detail={
                "code": "SCRAPE_FAILED",
                "message": "Could not extract product details. Please check the URL.",
            },
        )
    except Exception as exc:
        logger.error(f"Unexpected error — url={validated.canonical_url} error={str(exc)}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "UNKNOWN_ERROR",
                "message": "Something went wrong.",
            },
        )

    # Step 3 — assemble live_data from scrape result
    marketplace_product_id = (
        result.marketplace_product_id or validated.marketplace_product_id
    )
    scraped_at = datetime.now(timezone.utc)

    # ── DEBUG: log all result fields for tracing enrichment data flow ─────────
    logger.info(
        f"[PREVIEW][debug] scrape result fields — "
        f"extraction_method={result.extraction_method} "
        f"current_price={result.current_price} "
        f"mrp={getattr(result, 'mrp', 'ATTR_MISSING')} "
        f"special_price={getattr(result, 'special_price', 'ATTR_MISSING')} "
        f"discount_pct={getattr(result, 'discount_pct', 'ATTR_MISSING')} "
        f"offers_count={len(getattr(result, 'offers', []) or [])} "
        f"offers_preview={list(getattr(result, 'offers', []) or [])[:2]}"
    )

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
        # Affiliate API enrichment — present only when source=affiliate_api.
        # None for browser-scraped results; schema defaults handle the rest.
        mrp=getattr(result, "mrp", None),
        special_price=getattr(result, "special_price", None),
        discount_pct=getattr(result, "discount_pct", None),
        offers=getattr(result, "offers", []) or [],
    )

    # ── DEBUG: confirm enrichment fields made it into LiveData ────────────────
    logger.info(
        f"[PREVIEW][debug] LiveData built — "
        f"current_price={live_data.current_price} "
        f"mrp={live_data.mrp} "
        f"special_price={live_data.special_price} "
        f"discount_pct={live_data.discount_pct} "
        f"offers_count={len(live_data.offers)} "
        f"offers_preview={live_data.offers[:2]}"
    )

    # Step 4 — DB lookup after scrape (handles amzn.in short URL ASIN redirect)
    existing_after_scrape = None
    if marketplace_product_id and marketplace_product_id != validated.marketplace_product_id:
        existing_after_scrape = product_repo.get_by_platform_and_marketplace_id(
            validated.platform, marketplace_product_id
        )

    # ── Write product to DB immediately (PATH B) ──────────────────────────────
    # Product is written/updated at preview time — no confirmation needed.
    # confirm_subscription() will only add the subscription row.
    scraped_now = datetime.now(timezone.utc)
    affiliated_url = _build_affiliated_url(validated.canonical_url, validated.platform)

    # Re-check DB using the resolved marketplace_product_id
    db_product = existing_after_scrape or product_repo.get_by_platform_and_marketplace_id(
        validated.platform, marketplace_product_id
    )

    if db_product is None:
        # New product — create row
        db_product = product_repo.create(
            url=affiliated_url,
            platform=validated.platform,
            marketplace_product_id=marketplace_product_id,
            name=result.name,
            brand=result.brand,
            image_url=result.image_url,
            current_price=result.current_price,
            currency="INR",
            availability=result.availability,
            rating=result.rating,
            review_count=result.review_count,
            seller=result.seller,
            last_checked_at=scraped_now,
            product_metadata=getattr(result, "product_metadata", None) or {},
        )
        # Write affiliate enrichment
        product_repo.update_affiliate_data(
            db_product,
            mrp=getattr(result, "mrp", None),
            special_price=getattr(result, "special_price", None),
            discount_pct=getattr(result, "discount_pct", None),
            offers=getattr(result, "offers", []) or [],
        )
        # Write category
        incoming_category = getattr(result, "category", None)
        if incoming_category:
            product_repo.update_category(db_product, incoming_category)

        # First price history row
        ph_repo_preview = PriceHistoryRepository(db)
        ph_repo_preview.insert(
            product_id=db_product.product_id,
            price=result.current_price,
            scrape_status="success",
            run_id=None,
        )
        logger.info(
            f"[PREVIEW] PATH B — new product written to DB — "
            f"product_id={db_product.product_id} "
            f"platform={validated.platform}"
        )
    else:
        # Existing product — update metadata + affiliate fields
        product_repo.update_from_live_data(
            db_product,
            {
                "name":            result.name,
                "brand":           result.brand,
                "image_url":       result.image_url,
                "availability":    result.availability,
                "rating":          result.rating,
                "review_count":    result.review_count,
                "seller":          result.seller,
                "last_checked_at": scraped_now,
            },
        )
        product_repo.update_affiliate_data(
            db_product,
            mrp=getattr(result, "mrp", None),
            special_price=getattr(result, "special_price", None),
            discount_pct=getattr(result, "discount_pct", None),
            offers=getattr(result, "offers", []) or [],
        )
        # Write product_metadata — merge so existing richer data is preserved
        incoming_metadata = getattr(result, "product_metadata", None) or {}
        if incoming_metadata:
            merged = ScraperEngine.merge_metadata(
                existing=db_product.product_metadata,
                incoming=incoming_metadata,
            )
            product_repo.update_product_metadata(db_product, merged)
        if result.current_price is not None and result.current_price != db_product.current_price:
            product_repo.update_current_price(db_product, result.current_price)
        # Write category
        incoming_category = getattr(result, "category", None)
        if incoming_category:
            product_repo.update_category(db_product, incoming_category)
        logger.info(
            f"[PREVIEW] PATH B — existing product updated in DB — "
            f"product_id={db_product.product_id}"
        )

    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning(f"[PREVIEW] PATH B — DB write failed — error={exc}")

    is_new_product = db_product is not None

    catalog_data = None
    if db_product:
        catalog_data = _build_catalog_data(
            db_product, product_repo, live_price=result.current_price
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
        data_source="live_scrape",
        live_data=live_data,
        catalog_data=catalog_data,
    )


@router.get(
    "",
    response_model=ProductListOut,
    summary="List all products ordered by watcher count",
)
def list_products(
    platform: Optional[str] = Query(
        default=None,
        pattern="^(amazon|flipkart|myntra)$",
        description="Filter by platform. Omit for all platforms.",
    ),
    category: Optional[str] = Query(
        default=None,
        description=(
            "Filter by unified category. "
            "One of: mobiles, electronics, fashion, home, beauty, sports, books, toys, other. "
            "Omit for all categories. Multiple values not supported — call once per category."
        ),
    ),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> ProductListOut:
    """
    Return all products in the catalogue ordered by watcher count descending.
    No authentication required — public endpoint.
    Used by the /offers browsing page.

    Supports optional filtering by platform and/or category.
    """
    product_repo = ProductRepository(db)
    items_raw, total = product_repo.get_all(
        platform=platform,
        category=category,
        limit=limit,
        offset=offset,
    )
    items = [ProductListItem(**item) for item in items_raw]
    return ProductListOut(
        total=total,
        count=len(items),
        platform=platform,
        items=items,
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
    Retrieve full product details including watcher count, price stats,
    and price history for the chart.
    Used by all Refresh buttons — pure DB read, no scraping.
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

    ph_repo = PriceHistoryRepository(db)
    history_rows = ph_repo.get_for_product(product_id, limit=90)

    # Build column dict using DB column names, then override product_metadata
    # because SQLAlchemy's reserved 'metadata' attribute name means
    # getattr(product, 'metadata') returns the ORM metadata object, not our
    # JSONB column. We read it via the ORM attribute name 'product_metadata'.
    col_data = {
        c.name: getattr(product, c.name)
        for c in product.__table__.columns
        if c.name != "metadata"   # skip — read via ORM attribute below
    }

    return ProductOut(
        **col_data,
        product_metadata=product.product_metadata or {},
        watcher_count=watcher_count,
        price_stats=PriceStats(**price_stats_raw) if price_stats_raw else None,
        price_history=[
            PriceHistoryPoint(checked_at=row.checked_at, price=row.price)
            for row in history_rows
        ],
    )


# ---------------------------------------------------------------------------
# GET /products/{product_id}/history
# ---------------------------------------------------------------------------

_PERIOD_DAYS: dict[str, Optional[int]] = {
    "1m": 30,
    "3m": 90,
    "6m": 180,
    "all": None,
}


@router.get(
    "/{product_id}/history",
    response_model=PriceHistoryOut,
    summary="Get price history for a product",
)
def get_product_history(
    product_id: uuid.UUID,
    period: str = Query(
        default="3m",
        pattern="^(1m|3m|6m|all)$",
        description="Lookback window: '1m'=30d, '3m'=90d, '6m'=180d, 'all'=full history.",
    ),
    db: Session = Depends(get_db),
) -> PriceHistoryOut:
    """
    Return price history for a product filtered by period.

    Only rows with scrape_status='success' and price IS NOT NULL are included.
    Rows are returned oldest-first for the chart.
    Empty history list (not 404) when product exists but has no data yet.

    Raises:
        404 PRODUCT_NOT_FOUND: product_id does not exist.
        422 VALIDATION_ERROR: period is not one of '1m', '3m', '6m', 'all'.
    """
    product_repo = ProductRepository(db)
    product = product_repo.get_by_id(product_id)
    if product is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "PRODUCT_NOT_FOUND", "message": "Product not found."},
        )

    days = _PERIOD_DAYS[period]
    since: Optional[datetime] = None
    if days is not None:
        since = datetime.now(timezone.utc) - timedelta(days=days)

    ph_repo = PriceHistoryRepository(db)
    rows = ph_repo.get_for_product(product_id, since=since)

    history_points = [
        PriceHistoryPoint(price=row.price, checked_at=row.checked_at)
        for row in rows
    ]

    logger.info(
        f"Price history fetched — product_id={product_id} "
        f"period={period} count={len(history_points)}"
    )

    return PriceHistoryOut(
        product_id=product_id,
        period=period,
        count=len(history_points),
        history=history_points,
    )
