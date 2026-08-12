"""add_search_indexes

Revision ID: 72005865ef60
Revises: ced3bfc62de6
Create Date: 2026-08-11 17:03:09.970362

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '72005865ef60'
down_revision: Union[str, Sequence[str], None] = 'ced3bfc62de6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add GIN indexes for pg_trgm + full-text search on canonical_products. (v5.1)

    NOTE: pg_trgm extension must be enabled before running this migration.
          Run in Supabase SQL editor first:
              CREATE EXTENSION IF NOT EXISTS pg_trgm;

    No table or column changes — index-only migration.
    """
    # Trigram index on canonical_products.normalized_name
    # Powers similarity() in find_by_brand_and_name() and search()
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_canonical_products_normalized_name_trgm
        ON canonical_products
        USING gin (normalized_name gin_trgm_ops)
    """)

    # Full-text search index on canonical_products.normalized_name
    # Powers to_tsvector / plainto_tsquery in search()
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_canonical_products_normalized_name_fts
        ON canonical_products
        USING gin (to_tsvector('english', coalesce(normalized_name, '')))
    """)

    # Trigram index on canonical_products.brand
    # Replaces Python-side brand ilike scan in find_by_brand_and_name()
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_canonical_products_brand_trgm
        ON canonical_products
        USING gin (brand gin_trgm_ops)
    """)

    # Trigram index on products.normalized_name
    # Forward-looking for v5.2 listing-level search
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_products_normalized_name_trgm
        ON products
        USING gin (normalized_name gin_trgm_ops)
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_canonical_products_normalized_name_trgm")
    op.execute("DROP INDEX IF EXISTS ix_canonical_products_normalized_name_fts")
    op.execute("DROP INDEX IF EXISTS ix_canonical_products_brand_trgm")
    op.execute("DROP INDEX IF EXISTS ix_products_normalized_name_trgm")
