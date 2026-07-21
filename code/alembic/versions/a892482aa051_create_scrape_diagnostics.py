"""create_scrape_diagnostics

Revision ID: a892482aa051
Revises: 0c5ac6c429b0
Create Date: 2026-07-21 08:28:00.461705

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a892482aa051'
down_revision: Union[str, Sequence[str], None] = '0c5ac6c429b0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'scrape_diagnostics',
        sa.Column(
            'diagnostic_id',
            sa.UUID(),
            server_default=sa.text('gen_random_uuid()'),
            nullable=False,
        ),
        # ── Job linkage ───────────────────────────────────────────────────────
        # scrape_job_id: correlation UUID generated per scrape attempt in the worker.
        # Nullable — row is written even when no price_history row exists
        # (e.g. bot detection fires before DB write).
        sa.Column('scrape_job_id', sa.UUID(), nullable=True),
        sa.Column(
            'product_id',
            sa.UUID(),
            nullable=True,
        ),
        sa.Column('run_id', sa.UUID(), nullable=True),
        # ── Portal / worker context ───────────────────────────────────────────
        sa.Column('portal', sa.String(length=50), nullable=False),
        sa.Column('worker_id', sa.Integer(), nullable=True),
        sa.Column('attempt_number', sa.Integer(), nullable=False, server_default='1'),
        # ── Outcome ───────────────────────────────────────────────────────────
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('extraction_method', sa.String(length=50), nullable=True),
        sa.Column('error_type', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        # ── Layer diagnostics ─────────────────────────────────────────────────
        # Comma-separated layer names, e.g. "selector,json_ld"
        sa.Column('layers_attempted', sa.Text(), nullable=True),
        sa.Column('layers_failed', sa.Text(), nullable=True),
        # ── Timing (milliseconds) ─────────────────────────────────────────────
        sa.Column('navigation_ms', sa.Integer(), nullable=True),
        sa.Column('extraction_ms', sa.Integer(), nullable=True),
        sa.Column('total_duration_ms', sa.Integer(), nullable=True),
        # ── Timestamp ─────────────────────────────────────────────────────────
        sa.Column(
            'scraped_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text('now()'),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ['product_id'], ['products.product_id'], ondelete='CASCADE'
        ),
        sa.PrimaryKeyConstraint('diagnostic_id'),
    )
    # ── Indexes ───────────────────────────────────────────────────────────────
    # LayerStatsCache queries by portal + scraped_at range
    op.create_index(
        'ix_scrape_diagnostics_portal_scraped_at',
        'scrape_diagnostics',
        ['portal', 'scraped_at'],
    )
    # Purge job deletes old rows by scraped_at
    op.create_index(
        'ix_scrape_diagnostics_scraped_at',
        'scrape_diagnostics',
        ['scraped_at'],
    )
    # Link from price_history row to its diagnostic row
    op.create_index(
        'ix_scrape_diagnostics_scrape_job_id',
        'scrape_diagnostics',
        ['scrape_job_id'],
    )
    # Product-level diagnostic history lookup
    op.create_index(
        'ix_scrape_diagnostics_product_id',
        'scrape_diagnostics',
        ['product_id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_scrape_diagnostics_product_id', table_name='scrape_diagnostics')
    op.drop_index('ix_scrape_diagnostics_scrape_job_id', table_name='scrape_diagnostics')
    op.drop_index('ix_scrape_diagnostics_scraped_at', table_name='scrape_diagnostics')
    op.drop_index('ix_scrape_diagnostics_portal_scraped_at', table_name='scrape_diagnostics')
    op.drop_table('scrape_diagnostics')
