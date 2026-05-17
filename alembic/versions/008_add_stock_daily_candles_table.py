"""Add stock_daily_candles table

Revision ID: 008_stock_daily_candles
Revises: 007_stock_fundamentals
Create Date: 2026-05-17

KR 주식 일자별 OHLCV (pykrx get_market_ohlcv) 시계열 테이블.
PK는 (date, ticker_id) 멱등 UPSERT 키. 종목별 시계열 조회를 위해 (ticker_id, date) 보조 인덱스 추가.
기존 candle_daily MATERIALIZED VIEW(continuous aggregate)는 그대로 두고, 별도 테이블로 분리.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "008_stock_daily_candles"
down_revision: str | Sequence[str] | None = "007_stock_fundamentals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create stock_daily_candles table."""
    op.create_table(
        "stock_daily_candles",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False, comment="거래 영업일"),
        sa.Column("open", sa.Float(), nullable=False, comment="시가"),
        sa.Column("high", sa.Float(), nullable=False, comment="고가"),
        sa.Column("low", sa.Float(), nullable=False, comment="저가"),
        sa.Column("close", sa.Float(), nullable=False, comment="종가"),
        sa.Column("volume", sa.BigInteger(), nullable=False, comment="거래량(주)"),
        sa.Column("trade_value", sa.BigInteger(), nullable=True, comment="거래대금(원)"),
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
            ["ticker_id"], ["tickers.id"], name="fk_stock_daily_candles_ticker_id"
        ),
    )
    op.create_index(
        "ix_stock_daily_candles_ticker_id_date",
        "stock_daily_candles",
        ["ticker_id", "date"],
    )


def downgrade() -> None:
    """Drop stock_daily_candles table."""
    op.drop_index("ix_stock_daily_candles_ticker_id_date", table_name="stock_daily_candles")
    op.drop_table("stock_daily_candles")
