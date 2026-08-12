"""add_product_identity_graph

Revision ID: ced3bfc62de6
Revises: 6db88644e1b0
Create Date: 2026-08-11 15:03:34.401218

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'ced3bfc62de6'
down_revision: Union[str, Sequence[str], None] = '6db88644e1b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Create canonical_products table ───────────────────────────────────────
    op.create_table(
        'canonical_products',
        sa.Column('canonical_id', sa.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('normalized_name', sa.Text(), nullable=True),
        sa.Column('brand', sa.String(length=255), nullable=True),
        sa.Column('category', sa.String(length=50), server_default='other', nullable=False),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('model_number', sa.String(length=255), nullable=True),
        sa.Column('isbn', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('canonical_id'),
    )
    # Indexes on canonical_products — autogenerate missed these
    op.create_index('ix_canonical_products_model_number', 'canonical_products', ['model_number'], unique=False)
    op.create_index('ix_canonical_products_brand', 'canonical_products', ['brand'], unique=False)

    # ── Add columns to products ────────────────────────────────────────────────
    op.add_column('products', sa.Column('canonical_id', sa.UUID(), nullable=True))
    op.add_column('products', sa.Column('model_number', sa.String(length=255), nullable=True))
    op.add_column('products', sa.Column('normalized_name', sa.Text(), nullable=True))

    # ── Index + FK on products.canonical_id ───────────────────────────────────
    op.create_index(op.f('ix_products_canonical_id'), 'products', ['canonical_id'], unique=False)
    op.create_index('ix_products_model_number', 'products', ['model_number'], unique=False)
    op.create_foreign_key(
        'products_canonical_id_fkey',
        'products', 'canonical_products',
        ['canonical_id'], ['canonical_id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('products_canonical_id_fkey', 'products', type_='foreignkey')
    op.drop_index('ix_products_model_number', table_name='products')
    op.drop_index(op.f('ix_products_canonical_id'), table_name='products')
    op.drop_column('products', 'normalized_name')
    op.drop_column('products', 'model_number')
    op.drop_column('products', 'canonical_id')
    op.drop_index('ix_canonical_products_brand', table_name='canonical_products')
    op.drop_index('ix_canonical_products_model_number', table_name='canonical_products')
    op.drop_table('canonical_products')
