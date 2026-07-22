"""rename_success_to_status_in_scrape_diagnostics

Revision ID: e43fc4ac1a99
Revises: 162ce149d0da
Create Date: 2026-07-22 09:23:00.059746

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e43fc4ac1a99'
down_revision: Union[str, Sequence[str], None] = '162ce149d0da'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'scrape_diagnostics',
        'success',
        new_column_name='status',
        existing_type=sa.Boolean(),
        type_=sa.String(length=50),
        existing_nullable=False,
        nullable=True,
        postgresql_using="CASE WHEN success THEN 'success' ELSE 'failed' END",
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'scrape_diagnostics',
        'status',
        new_column_name='success',
        existing_type=sa.String(length=50),
        type_=sa.Boolean(),
        existing_nullable=True,
        nullable=False,
        postgresql_using="status = 'success'",
    )
