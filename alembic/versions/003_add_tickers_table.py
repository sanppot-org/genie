"""Add tickers table for managing asset symbols

Revision ID: 003_tickers
Revises: 002_exchanges
Create Date: 2025-01-09

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

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
        sa.Column("exchange_id", sa.Integer(), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", name="uix_ticker"),
        sa.ForeignKeyConstraint(["exchange_id"], ["exchanges.id"], name="fk_tickers_exchange_id"),
    )

    # Create indexes for faster lookups
    op.create_index("ix_tickers_exchange_id", "tickers", ["exchange_id"])
    op.create_index("ix_tickers_asset_type", "tickers", ["asset_type"])

    # Create trigger for auto-updating updated_at
    op.execute("""
               CREATE TRIGGER trigger_tickers_updated_at
                   BEFORE UPDATE
                   ON tickers
                   FOR EACH ROW
               EXECUTE FUNCTION update_updated_at_column();
               """)


def downgrade() -> None:
    """Drop tickers table."""
    op.drop_index("ix_tickers_asset_type", table_name="tickers")
    op.drop_index("ix_tickers_exchange_id", table_name="tickers")
    op.drop_table("tickers")
