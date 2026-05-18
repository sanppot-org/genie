"""Drop stock_dividends.dividend_yield column

Revision ID: 010_drop_dividend_yield
Revises: 009_stock_dividends
Create Date: 2026-05-18

KIS `ksdinfo_dividend`의 divi_rate가 "액면가 대비 현금배당률(%)"로 확인되어
시가배당률과 의미가 다름. 시가배당률은 이미 `StockFundamental.div`(pykrx)에 일자별로 적재되므로
`stock_dividends.dividend_yield` 컬럼을 제거한다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "010_drop_dividend_yield"
down_revision: str | Sequence[str] | None = "009_stock_dividends"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Drop dividend_yield column."""
    op.drop_column("stock_dividends", "dividend_yield")


def downgrade() -> None:
    """Restore dividend_yield column (nullable)."""
    op.add_column(
        "stock_dividends",
        sa.Column("dividend_yield", sa.Float(), nullable=True, comment="시가배당률(%)"),
    )
