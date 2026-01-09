"""Add tickers table for managing asset symbols

Revision ID: 002_tickers
Revises: 001_initial
Create Date: 2025-01-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003_tickers"
down_revision: str | Sequence[str] | None = "002_exchanges"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create tickers table."""
    op.create_table(
        "tickers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=20), nullable=False),
        sa.Column("asset_type", sa.String(length=20), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", name="uix_ticker"),
    )
    op.create_index(op.f("ix_tickers_ticker"), "tickers", ["ticker"])
    op.create_index(op.f("ix_tickers_asset_type"), "tickers", ["asset_type"])


def downgrade() -> None:
    """Drop tickers table."""
    op.drop_index(op.f("ix_tickers_asset_type"), table_name="tickers")
    op.drop_index(op.f("ix_tickers_ticker"), table_name="tickers")
    op.drop_table("tickers")
