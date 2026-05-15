"""Add industry_code column to tickers

Revision ID: 006_tickers_industry_code
Revises: 005_tickers_name_active
Create Date: 2026-05-15

Adds nullable `industry_code` (KSIC code from DART OpenAPI) column to tickers.
DART 미조회/실패 허용을 위해 nullable로 둔다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_tickers_industry_code"
down_revision: str | Sequence[str] | None = "005_tickers_name_active"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add industry_code column to tickers."""
    op.add_column(
        "tickers",
        sa.Column("industry_code", sa.String(length=8), nullable=True),
    )


def downgrade() -> None:
    """Drop industry_code column from tickers."""
    op.drop_column("tickers", "industry_code")
