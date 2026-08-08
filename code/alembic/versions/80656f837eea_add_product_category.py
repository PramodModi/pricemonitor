"""add-product-category

Revision ID: 80656f837eea
Revises: e8d4f84f775b
Create Date: 2026-08-08 17:01:09.868899

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '80656f837eea'
down_revision: Union[str, Sequence[str], None] = 'e8d4f84f775b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'products',
        sa.Column('category', sa.String(length=50), server_default='other', nullable=False)
    )


def downgrade() -> None:
    op.drop_column('products', 'category')
