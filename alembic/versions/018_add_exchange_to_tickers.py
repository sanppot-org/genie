"""Add exchange column to tickers

Revision ID: 018_ticker_exchange
Revises: 017_adjusted_candle_columns
Create Date: 2026-06-17

해외 거래소코드(KIS EXCD: NAS/NYS/AMS) 저장 컬럼. US_STOCK만 채워지고 그 외 자산은 NULL.
nullable ADD COLUMN이라 테이블 rewrite 없는 메타데이터 변경(잠금 최소).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "018_ticker_exchange"
down_revision: str | Sequence[str] | None = "017_adjusted_candle_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable exchange column."""
    op.add_column(
        "tickers",
        sa.Column("exchange", sa.String(length=4), nullable=True, comment="해외 거래소코드(KIS EXCD: NAS/NYS/AMS), US_STOCK만 채워짐"),
    )


def downgrade() -> None:
    """Drop exchange column."""
    op.drop_column("tickers", "exchange")
