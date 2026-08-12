"""
Search endpoint — v5.1

File: app/fastapi/api/v1/search.py

GET /v1/search?q=samsung+galaxy+s24&limit=20

Returns canonical products matching the query, with all portal listings
attached to each result. The frontend uses this when the user types a
product name (not a URL) into the Track page search box.

Design:
  - Query runs entirely in PostgreSQL via pg_trgm + tsvector indexes
  - Two-query approach: search canonicals → batch fetch listings (no N+1)
  - Returns empty list (not 404) when no results found
  - Minimum threshold 0.15 trgm OR any FTS match — generous to catch partials
  - Results ordered by combined_score DESC (trgm * 0.6 + fts * 0.4)
  - f-strings only for logging (DEV-006)
"""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.repositories.canonical_product_repo import CanonicalProductRepository
from app.utils.logging import get_logger

router = APIRouter(prefix="/search", tags=["search"])
logger = get_logger(__name__)


# ── Response schemas ──────────────────────────────────────────────────────────

class PortalListing(BaseModel):
    """One portal listing attached to a canonical search result."""
    product_id: uuid.UUID
    platform: str
    current_price: Optional[float] = None
    mrp: Optional[float] = None
    special_price: Optional[float] = None
    url: str
    availability: Optional[bool] = None
    last_checked_at: Optional[str] = None   # ISO string — formatted by serializer

    model_config = {"from_attributes": True}


class SearchResult(BaseModel):
    """One canonical product with all its portal listings."""
    canonical_id: uuid.UUID
    name: Optional[str] = None              # canonical normalized_name
    brand: Optional[str] = None
    category: Optional[str] = None
    image_url: Optional[str] = None
    model_number: Optional[str] = None
    best_price: Optional[float] = None      # lowest current_price across listings
    best_platform: Optional[str] = None     # platform with best_price
    listings: list[PortalListing] = []


class SearchResponse(BaseModel):
    """Top-level search response."""
    query: str
    count: int
    results: list[SearchResult]


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=SearchResponse,
    summary="Search products by name",
)
def search_products(
    q: str = Query(
        ...,
        min_length=2,
        max_length=200,
        description="Product name to search for. Min 2 chars.",
    ),
    limit: int = Query(
        default=20,
        ge=1,
        le=50,
        description="Max results to return (1–50).",
    ),
    db: Session = Depends(get_db),
) -> SearchResponse:
    """
    Search canonical products by name using PostgreSQL trigram + full-text search.

    Accepts a free-text product name query. Returns canonical products ranked by
    combined trigram + FTS score, each with all tracked portal listings attached.

    This endpoint is used by the Track page when the user types a product name
    instead of pasting a URL. The frontend detects text vs URL and routes here.

    Response shape per result:
        canonical_id, name, brand, category, image_url, model_number,
        best_price (lowest across portals), best_platform,
        listings: [{product_id, platform, current_price, mrp, special_price,
                    url, availability, last_checked_at}]

    Empty results list (not 404) when no matches found.
    """
    logger.info(f"[SEARCH] query={q!r} limit={limit}")

    repo = CanonicalProductRepository(db)

    # ── Step 1: search canonical_products via pg_trgm + tsvector ─────────────
    raw_results = repo.search(query=q, limit=limit)

    if not raw_results:
        logger.info(f"[SEARCH] no results — query={q!r}")
        return SearchResponse(query=q, count=0, results=[])

    canonical_ids = [r["canonical_id"] for r in raw_results]
    logger.info(
        f"[SEARCH] found {len(canonical_ids)} canonicals — query={q!r} "
        f"top_score={raw_results[0].get('combined_score', 0):.3f}"
    )

    # ── Step 2: batch fetch all portal listings for found canonicals ──────────
    # One query for all canonical_ids — no N+1.
    listings_by_canonical = repo.get_listings_for_canonicals(canonical_ids)

    # ── Step 3: assemble response ─────────────────────────────────────────────
    results: list[SearchResult] = []

    for row in raw_results:
        cid = row["canonical_id"]
        raw_listings = listings_by_canonical.get(cid, [])

        portal_listings = [
            PortalListing(
                product_id=l["product_id"],
                platform=l["platform"],
                current_price=float(l["current_price"]) if l["current_price"] is not None else None,
                mrp=float(l["mrp"]) if l["mrp"] is not None else None,
                special_price=float(l["special_price"]) if l["special_price"] is not None else None,
                url=l["url"],
                availability=l["availability"],
                last_checked_at=(
                    l["last_checked_at"].isoformat()
                    if l["last_checked_at"] is not None
                    else None
                ),
            )
            for l in raw_listings
        ]

        # best_price = lowest current_price across all listings
        # listings are already ordered cheapest-first from the DB query
        best_price = None
        best_platform = None
        if portal_listings:
            cheapest = next(
                (l for l in portal_listings if l.current_price is not None),
                None,
            )
            if cheapest:
                best_price = cheapest.current_price
                best_platform = cheapest.platform

        results.append(
            SearchResult(
                canonical_id=cid,
                name=row.get("normalized_name"),
                brand=row.get("brand"),
                category=row.get("category"),
                image_url=row.get("image_url"),
                model_number=row.get("model_number"),
                best_price=best_price,
                best_platform=best_platform,
                listings=portal_listings,
            )
        )

    logger.info(
        f"[SEARCH] returning {len(results)} results — query={q!r}"
    )

    return SearchResponse(query=q, count=len(results), results=results)
