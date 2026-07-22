"""add_url_and_price_found_to_scrape_diagnostics

Revision ID: 162ce149d0da
Revises: 64077cc5d516
Create Date: 2026-07-22 09:16:54.987717

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '162ce149d0da'
down_revision: Union[str, Sequence[str], None] = '64077cc5d516'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'scrape_diagnostics',
        sa.Column('url', sa.Text(), nullable=True),
    )
    op.add_column(
        'scrape_diagnostics',
        sa.Column('price_found', sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('scrape_diagnostics', 'price_found')
    op.drop_column('scrape_diagnostics', 'url')
