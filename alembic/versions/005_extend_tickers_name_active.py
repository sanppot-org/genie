"""Extend tickers with name and active columns

Revision ID: 005_tickers_name_active
Revises: 004_data_source
Create Date: 2026-05-15

This migration:
1. Adds `name` column to tickers for display name (e.g., "삼성전자").
   Existing rows are backfilled with the `ticker` value, then the column
   is altered to NOT NULL.
2. Adds `active` column (NOT NULL, default TRUE) to tickers for soft-delete
   semantics when a stock is delisted.

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "005_tickers_name_active"
down_revision: str | Sequence[str] | None = "004_data_source"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add name and active columns to tickers."""
    op.add_column(
        "tickers",
        sa.Column("name", sa.String(length=100), nullable=True),
    )
    op.execute("UPDATE tickers SET name = ticker WHERE name IS NULL")
    op.alter_column("tickers", "name", nullable=False)

    op.add_column(
        "tickers",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade() -> None:
    """Drop name and active columns from tickers."""
    op.drop_column("tickers", "active")
    op.drop_column("tickers", "name")
