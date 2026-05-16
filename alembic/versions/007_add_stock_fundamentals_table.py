"""Add stock_fundamentals table

Revision ID: 007_stock_fundamentals
Revises: 006_tickers_industry_code
Create Date: 2026-05-16

일자별 종목 펀더멘털(pykrx get_market_fundamental: BPS/PER/PBR/EPS/DIV/DPS) 시계열 테이블.
PK는 (date, ticker_id) 멱등 UPSERT 키. 종목별 시계열 조회를 위해 (ticker_id, date) 보조 인덱스 추가.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "007_stock_fundamentals"
down_revision: str | Sequence[str] | None = "006_tickers_industry_code"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create stock_fundamentals table."""
    op.create_table(
        "stock_fundamentals",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False, comment="펀더멘털 기준 영업일"),
        sa.Column("bps", sa.Float(), nullable=True, comment="주당순자산가치 (Book-value Per Share)"),
        sa.Column("per", sa.Float(), nullable=True, comment="주가수익률 = 주가 / EPS, 적자면 None"),
        sa.Column("pbr", sa.Float(), nullable=True, comment="주가순자산배수 = 주가 / BPS"),
        sa.Column("eps", sa.Float(), nullable=True, comment="주당순이익 (Earnings Per Share)"),
        sa.Column("div", sa.Float(), nullable=True, comment="배당수익률(%) = DPS / 주가"),
        sa.Column("dps", sa.Float(), nullable=True, comment="주당배당금 (Dividend Per Share)"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("date", "ticker_id"),
        sa.ForeignKeyConstraint(
            ["ticker_id"], ["tickers.id"], name="fk_stock_fundamentals_ticker_id"
        ),
    )
    op.create_index(
        "ix_stock_fundamentals_ticker_id_date",
        "stock_fundamentals",
        ["ticker_id", "date"],
    )


def downgrade() -> None:
    """Drop stock_fundamentals table."""
    op.drop_index("ix_stock_fundamentals_ticker_id_date", table_name="stock_fundamentals")
    op.drop_table("stock_fundamentals")
