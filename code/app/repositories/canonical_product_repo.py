"""
CanonicalProductRepository — DB access for canonical_products table.
 
File: app/repositories/canonical_product_repo.py
 
All methods use db.flush() not db.commit() — caller owns the transaction.
 
v5.1: find_by_brand_and_name() replaced with PostgreSQL pg_trgm trigram query.
      search() method added for GET /v1/search endpoint.
      pg_trgm extension must be enabled in Supabase before using these methods.
v5.3: search() rewritten — FTS primary filter, trgm fallback, category-aware
      re-ranking. _extract_query_category() imports _RULES from category_mapper
      so keyword additions there automatically flow into search scoring.
"""
 
import uuid
from typing import Optional
 
from sqlalchemy import select, text
from sqlalchemy.orm import Session
 
from app.core.models.canonical_product import CanonicalProduct
from app.scraper_v2.scrapers.category_mapper import _RULES
 
 

def _extract_query_category(query: str) -> "Optional[str]":
    """
    Extract intended product category from a free-text search query.

    Reuses _RULES from category_mapper — the same keyword list that maps
    portal breadcrumbs to category slugs. Longer keywords are checked first
    so "washing machine" matches before "machine" could match something else.

    Returns a category slug (e.g. "appliances", "mobiles") or None when
    the query contains no recognisable category keyword.

    Future-proof: adding keywords to category_mapper._RULES automatically
    improves search ranking with zero changes here.
    """
    if not query:
        return None
    needle = query.lower().strip()
    # Sort by keyword length descending — longest match wins.
    for keyword, slug in sorted(_RULES, key=lambda r: -len(r[0])):
        if keyword in needle:
            return slug
    return None

class CanonicalProductRepository:
 
    def __init__(self, db: Session) -> None:
        self.db = db
 
    def get_by_id(self, canonical_id: uuid.UUID) -> Optional[CanonicalProduct]:
        return self.db.get(CanonicalProduct, canonical_id)
 
    def find_by_model_number(self, model_number: str) -> Optional[CanonicalProduct]:
        """
        Exact match on model_number. Case-insensitive via UPPER().
        Primary cross-portal match key for electronics/footwear.
        Returns None when not found — caller creates a new canonical product.
        """
        if not model_number or not model_number.strip():
            return None
        return self.db.scalar(
            select(CanonicalProduct).where(
                CanonicalProduct.model_number == model_number.strip().upper()
            )
        )
 
    def find_by_isbn(self, isbn: str) -> Optional[CanonicalProduct]:
        """
        Exact match on ISBN. For books only.
        Strips hyphens before comparison (ISBN-13: 978-0-306-40615-7 → 9780306406157).
        """
        if not isbn:
            return None
        clean = isbn.replace("-", "").replace(" ", "").strip()
        return self.db.scalar(
            select(CanonicalProduct).where(CanonicalProduct.isbn == clean)
        )
 
    def find_by_brand_and_name(
        self,
        brand: str,
        normalized_name: str,
        threshold: float = 0.85,
    ) -> Optional[CanonicalProduct]:
        """
        Fuzzy name match within the same brand using PostgreSQL pg_trgm. (v5.1)
 
        Replaces the Python-side Jaccard scan from v5.0. The trigram index on
        canonical_products.normalized_name makes this a pure index scan — no
        full table fetch, no Python-side scoring loop.
 
        Strategy:
          1. Filter by brand (case-insensitive exact match — brand index covers this)
          2. Score remaining rows by trigram similarity against normalized_name
          3. Return the best match above threshold, or None
 
        The pg_trgm similarity() function returns 0.0–1.0. Default threshold 0.85
        matches the previous Jaccard threshold — same selectivity, faster execution.
 
        Args:
            brand:           Brand name to match (case-insensitive).
            normalized_name: Cleaned product name (specs stripped).
            threshold:       Minimum trigram similarity (0.0–1.0). Default 0.85.
 
        Returns:
            Best-matching CanonicalProduct or None.
 
        Requires:
            pg_trgm extension enabled in PostgreSQL (CREATE EXTENSION pg_trgm).
            ix_canonical_products_normalized_name_trgm index (v5.1 migration).
        """
        if not brand or not normalized_name:
            return None
 
        # Use raw SQL for pg_trgm similarity() function — not available in
        # SQLAlchemy ORM without custom type extensions.
        # Parameters are passed as bound values — no SQL injection risk.
        row = self.db.execute(
            text("""
                SELECT
                    canonical_id,
                    similarity(normalized_name, :name) AS score
                FROM canonical_products
                WHERE
                    brand ILIKE :brand
                    AND normalized_name IS NOT NULL
                    AND similarity(normalized_name, :name) >= :threshold
                ORDER BY score DESC
                LIMIT 1
            """),
            {
                "brand": brand.strip(),
                "name": normalized_name.strip(),
                "threshold": threshold,
            },
        ).first()
 
        if row is None:
            return None
 
        return self.db.get(CanonicalProduct, row.canonical_id)
 
    def search(
        self,
        query: str,
        limit: int = 20,
    ) -> list[dict]:
        """
        Hybrid FTS + trigram search with category-aware re-ranking. (v5.3)

        Three-pass strategy:

        Pass 1 — FTS primary (websearch_to_tsquery):
          PostgreSQL full-text search against the pre-built fts tsvector column.
          Handles stemming ("grinders" -> "grind"), word order, boolean operators.
          Fast — uses the ix_canonical_products_fts GIN index directly.
          Best for natural language queries: "bosch mixer grinder 1000w".

        Pass 2 — trgm fallback (threshold 0.15):
          Only runs when FTS returns 0 results. Handles:
            - Typos ("samsng galaxy") — trgm is typo-tolerant
            - Model number queries ("MGM8842MIN") — not in tsvector vocabulary
            - Very short / single-word queries ("bosch") — low FTS signal

        Pass 3 — category-aware re-ranking (Python side):
          Extracts intended category from the query using _RULES from
          category_mapper.py (e.g. "mixer grinder" -> "appliances").
          Results whose category matches get a +0.25 boost to combined_score.
          Re-sorts in Python — no extra DB round-trip.
          Future-proof: adding keywords to category_mapper._RULES automatically
          improves search ranking with zero changes here.

        Scoring:
          DB score    = fts_rank * 0.6 + trgm_score * 0.4
          Final score = db_score + (0.25 if category matches else 0.0)

        Args:
            query: Raw user search string (e.g. "bosch mixer grinder").
            limit: Max results to return (1-20).

        Returns:
            List of dicts with canonical product fields + final_score.
            Sorted by final_score DESC. Empty list when no results.

        Requires:
            pg_trgm extension + ix_canonical_products_normalized_name_trgm
            ix_canonical_products_fts GIN index (v5.1 migration).
        """
        if not query or not query.strip():
            return []

        q = query.strip()
        # Fetch extra rows before re-ranking so top-limit after boost is correct
        params = {"query": q, "limit": limit * 2}

        # ── Pass 1 — FTS primary ──────────────────────────────────────────────
        # websearch_to_tsquery accepts natural language — quotes, OR, minus.
        # fts column is a pre-built tsvector — no per-row to_tsvector() call.
        # Combines FTS rank (0.6) with trgm similarity (0.4) for scoring.
        FTS_SQL = """
            SELECT
                canonical_id,
                normalized_name,
                brand,
                category,
                image_url,
                model_number,
                isbn,
                created_at,
                coalesce(similarity(normalized_name, :query), 0)        AS trgm_score,
                coalesce(ts_rank(fts, websearch_to_tsquery('english', :query)), 0)
                                                                        AS fts_rank,
                (
                    coalesce(ts_rank(fts, websearch_to_tsquery('english', :query)), 0) * 0.6
                    + coalesce(similarity(normalized_name, :query), 0) * 0.4
                )                                                       AS combined_score
            FROM canonical_products
            WHERE
                normalized_name IS NOT NULL
                AND fts @@ websearch_to_tsquery('english', :query)
            ORDER BY combined_score DESC
            LIMIT :limit
        """
        rows = self.db.execute(text(FTS_SQL), params).mappings().all()

        # ── Pass 2 — trgm fallback ────────────────────────────────────────────
        # Only when FTS returns nothing — handles typos and model numbers.
        # trgm threshold 0.15: low enough for short brand queries ("bosch"),
        # tight enough to exclude completely unrelated products.
        if not rows:
            TRGM_SQL = """
                SELECT
                    canonical_id,
                    normalized_name,
                    brand,
                    category,
                    image_url,
                    model_number,
                    isbn,
                    created_at,
                    similarity(normalized_name, :query)                 AS trgm_score,
                    coalesce(ts_rank(
                        to_tsvector('english',
                            coalesce(normalized_name, '') || ' ' ||
                            coalesce(brand, '') || ' ' ||
                            coalesce(model_number, '')
                        ),
                        websearch_to_tsquery('english', :query)
                    ), 0)                                               AS fts_rank,
                    (
                        similarity(normalized_name, :query) * 0.6
                        + coalesce(ts_rank(
                            to_tsvector('english',
                                coalesce(normalized_name, '') || ' ' ||
                                coalesce(brand, '') || ' ' ||
                                coalesce(model_number, '')
                            ),
                            websearch_to_tsquery('english', :query)
                        ), 0) * 0.4
                    )                                                   AS combined_score
                FROM canonical_products
                WHERE
                    normalized_name IS NOT NULL
                    AND similarity(normalized_name, :query) > 0.15
                ORDER BY combined_score DESC
                LIMIT :limit
            """
            rows = self.db.execute(text(TRGM_SQL), params).mappings().all()

        if not rows:
            return []

        # ── Pass 3 — category-aware re-ranking (Python) ───────────────────────
        # Extract intended category from query — reuses _RULES from
        # category_mapper so no separate keyword list to maintain.
        intended_category = _extract_query_category(q)

        results = []
        for r in rows:
            d = dict(r)
            # Boost results whose stored category matches query intent
            category_boost = (
                0.25
                if intended_category and d.get("category") == intended_category
                else 0.0
            )
            d["final_score"] = d["combined_score"] + category_boost
            d["intended_category"] = intended_category  # for debug logging
            results.append(d)

        # Re-sort by final_score descending, trim to requested limit
        results.sort(key=lambda x: x["final_score"], reverse=True)
        return results[:limit]

    def get_listings_for_canonicals(
        self,
        canonical_ids: list[uuid.UUID],
    ) -> dict[uuid.UUID, list[dict]]:
        """
        Fetch all portal listings (products rows) for a set of canonical_ids.
        Returns a dict mapping canonical_id → list of listing dicts.
 
        Used by the search endpoint to attach portal prices to each canonical
        result without an N+1 query — one batch query for all results.
 
        Only returns listings where current_price IS NOT NULL (product was
        scraped successfully at least once).
        """
        if not canonical_ids:
            return {}
 
        from app.core.models.product import Product
 
        rows = self.db.execute(
            select(
                Product.canonical_id,
                Product.product_id,
                Product.platform,
                Product.current_price,
                Product.mrp,
                Product.special_price,
                Product.url,
                Product.availability,
                Product.last_checked_at,
            ).where(
                Product.canonical_id.in_(canonical_ids),
                Product.current_price.isnot(None),
            ).order_by(
                Product.canonical_id,
                Product.current_price.asc(),   # cheapest first per canonical
            )
        ).mappings().all()
 
        result: dict[uuid.UUID, list[dict]] = {}
        for row in rows:
            cid = row["canonical_id"]
            if cid not in result:
                result[cid] = []
            result[cid].append(dict(row))
        return result
 
    def create(
        self,
        normalized_name: Optional[str] = None,
        brand: Optional[str] = None,
        category: str = "other",
        image_url: Optional[str] = None,
        model_number: Optional[str] = None,
        isbn: Optional[str] = None,
    ) -> CanonicalProduct:
        """
        Create a new canonical product row.
        Called when no existing canonical product matches the scrape result.
        """
        canonical = CanonicalProduct(
            normalized_name=normalized_name,
            brand=brand,
            category=category,
            image_url=image_url,
            model_number=model_number.strip().upper() if model_number else None,
            isbn=isbn.replace("-", "").strip() if isbn else None,
        )
        self.db.add(canonical)
        self.db.flush()
        return canonical
 
    def update_image(
        self,
        canonical: CanonicalProduct,
        image_url: str,
    ) -> CanonicalProduct:
        """Update image when a higher-quality one is found."""
        canonical.image_url = image_url
        self.db.flush()
        return canonical