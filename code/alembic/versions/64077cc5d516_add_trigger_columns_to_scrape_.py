"""add_trigger_columns_to_scrape_diagnostics

Revision ID: 64077cc5d516
Revises: a892482aa051
Create Date: 2026-07-22 08:57:33.520837

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64077cc5d516'
down_revision: Union[str, Sequence[str], None] = 'a892482aa051'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'scrape_diagnostics',
        sa.Column(
            'trigger',
            sa.String(length=50),
            nullable=True,
            comment="scheduler | preview",
        ),
    )
    op.add_column(
        'scrape_diagnostics',
        sa.Column(
            'triggered_by',
            sa.String(length=255),
            nullable=True,
            comment="'Github' for cron runs, user email for preview, null if unknown",
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('scrape_diagnostics', 'triggered_by')
    op.drop_column('scrape_diagnostics', 'trigger')
