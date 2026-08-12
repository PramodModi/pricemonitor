"""
backfill_identity.py — one-time script to identity-link existing products.

Run from the project root:
    python -m app.scripts.backfill_identity

Or directly:
    cd /path/to/code
    python backfill_identity.py

What it does:
    Finds all products where canonical_id IS NULL and runs ProductIdentityService
    on each one — exactly the same logic as the v5.1 cron DEF-001 fix, but applied
    to the full existing catalog in one pass.

    After this script completes, GET /v1/search will return all products.

    Safe to re-run — products that already have canonical_id are skipped.
    Does not re-scrape — uses data already in the DB (name, brand, category,
    product_metadata.specs). No network calls.

Requirements:
    - pg_trgm extension enabled in Supabase (already done)
    - v5.1 migration applied (72005865ef60_add_search_indexes)
    - SUPABASE_DB_URL or DATABASE_URL env var set (same as FastAPI)

Progress:
    Logs one line per product. Run with LOG_LEVEL=INFO to see progress.
    Commits every 50 products to avoid holding a long transaction.
"""

import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("backfill_identity")


def run() -> None:
    from sqlalchemy import select
    from app.core.database import SessionLocal
    from app.core.models.product import Product
    from app.repositories.product_repo import ProductRepository
    from app.services.product_identity import product_identity_service

    db = SessionLocal()
    try:
        # ── Fetch all products with no canonical_id ────────────────────────────
        products = db.scalars(
            select(Product)
            .where(Product.canonical_id.is_(None))
            .order_by(Product.created_at.asc())
        ).all()

        total = len(products)
        logger.info(f"Found {total} products with canonical_id=NULL — starting backfill")

        linked = 0
        skipped = 0
        failed = 0
        BATCH_SIZE = 50

        for i, product in enumerate(products, start=1):
            try:
                product_repo = ProductRepository(db)

                # Pull specs from stored product_metadata
                specs = (product.product_metadata or {}).get("specs", {})

                canonical = product_identity_service.find_or_create_canonical(
                    db=db,
                    platform=product.platform,
                    name=product.name,
                    brand=product.brand,
                    category=product.category or "other",
                    image_url=product.image_url,
                    specs=specs,
                )

                if canonical is None:
                    # No name and no brand — can't create a meaningful canonical
                    logger.warning(
                        f"[{i}/{total}] skipped — no name/brand — "
                        f"product_id={product.product_id} "
                        f"platform={product.platform}"
                    )
                    skipped += 1
                    continue

                product_repo.update_canonical_id(product, canonical.canonical_id)

                # Backfill model_number — prefer specs extraction, fall back to canonical
                model_number = product_identity_service.extract_model_number(specs)
                if model_number is None:
                    model_number = canonical.model_number

                normalized = product_identity_service.normalize_name(
                    product.name or "", product.brand or "", specs
                )

                if model_number:
                    product_repo.update_model_number(product, model_number)
                if normalized:
                    product_repo.update_normalized_name(product, normalized)

                logger.info(
                    f"[{i}/{total}] linked — "
                    f"product_id={product.product_id} "
                    f"platform={product.platform} "
                    f"canonical_id={canonical.canonical_id} "
                    f"model_number={model_number!r} "
                    f"name={product.name!r:.50}"
                )
                linked += 1

                # Commit every BATCH_SIZE products to avoid a giant transaction
                if i % BATCH_SIZE == 0:
                    db.commit()
                    logger.info(f"── committed batch {i // BATCH_SIZE} ({i}/{total}) ──")

            except Exception as exc:
                logger.error(
                    f"[{i}/{total}] error — "
                    f"product_id={product.product_id} "
                    f"error={type(exc).__name__}: {exc}"
                )
                db.rollback()
                failed += 1
                # Re-open session state after rollback so remaining products work
                db.expire_all()

        # Final commit for the last partial batch
        try:
            db.commit()
        except Exception as exc:
            logger.error(f"Final commit failed — {exc}")
            db.rollback()

        logger.info(
            f"Backfill complete — "
            f"total={total} linked={linked} skipped={skipped} failed={failed}"
        )

    finally:
        db.close()


if __name__ == "__main__":
    run()
