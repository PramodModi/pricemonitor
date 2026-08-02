"""add_affiliate_fields_to_products

Revision ID: b3f9d12e4c71
Revises: e43fc4ac1a99
Create Date: 2026-08-02 10:43:42.855050

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'b3f9d12e4c71'
down_revision: Union[str, Sequence[str], None] = 'e43fc4ac1a99'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add affiliate enrichment columns to products table."""
    op.add_column(
        'products',
        sa.Column('mrp', sa.Numeric(precision=10, scale=2), nullable=True,
                  comment='Maximum Retail Price from affiliate API'),
    )
    op.add_column(
        'products',
        sa.Column('special_price', sa.Numeric(precision=10, scale=2), nullable=True,
                  comment='Price after bank/card offers (flipkartSpecialPrice)'),
    )
    op.add_column(
        'products',
        sa.Column('discount_pct', sa.Numeric(precision=5, scale=2), nullable=True,
                  comment='Discount percentage off MRP'),
    )
    op.add_column(
        'products',
        sa.Column('offers', postgresql.ARRAY(sa.Text()), nullable=True,
                  comment='Raw promotional offer strings from affiliate API'),
    )


def downgrade() -> None:
    """Remove affiliate enrichment columns from products table."""
    op.drop_column('products', 'offers')
    op.drop_column('products', 'discount_pct')
    op.drop_column('products', 'special_price')
    op.drop_column('products', 'mrp')
