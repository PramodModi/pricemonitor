"""add_canonical_url_to_products

Revision ID: 6db88644e1b0
Revises: 80656f837eea
Create Date: 2026-08-10 22:41:39.784931

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6db88644e1b0'
down_revision: Union[str, Sequence[str], None] = '80656f837eea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('products', sa.Column('canonical_url', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('products', 'canonical_url')
