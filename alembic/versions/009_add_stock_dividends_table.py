"""Add stock_dividends table

Revision ID: 009_stock_dividends
Revises: 008_stock_daily_candles
Create Date: 2026-05-18

KIS ksdinfo_dividend 기반 배당 이력 시계열 테이블.
PK는 (ticker_id, record_date, kind) 멱등 UPSERT 키.
종목별 시계열 조회를 위해 (ticker_id, record_date) 보조 인덱스 추가.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "009_stock_dividends"
down_revision: str | Sequence[str] | None = "008_stock_daily_candles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create stock_dividends table."""
    op.create_table(
        "stock_dividends",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("record_date", sa.Date(), nullable=False, comment="배당 기준일"),
        sa.Column("pay_date", sa.Date(), nullable=True, comment="배당 지급일"),
        sa.Column("dps", sa.Float(), nullable=False, comment="주당 배당금 (원)"),
        sa.Column("kind", sa.String(length=16), nullable=False, comment="SETTLE: 결산, INTERIM: 중간/분기"),
        sa.Column("dividend_yield", sa.Float(), nullable=True, comment="시가배당률(%)"),
        sa.Column("fiscal_year", sa.Integer(), nullable=False, comment="회계연도 (record_date 기준)"),
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
        sa.PrimaryKeyConstraint("ticker_id", "record_date", "kind"),
        sa.ForeignKeyConstraint(
            ["ticker_id"], ["tickers.id"], name="fk_stock_dividends_ticker_id"
        ),
    )
    op.create_index(
        "ix_stock_dividends_ticker_id_record_date",
        "stock_dividends",
        ["ticker_id", "record_date"],
    )


def downgrade() -> None:
    """Drop stock_dividends table."""
    op.drop_index("ix_stock_dividends_ticker_id_record_date", table_name="stock_dividends")
    op.drop_table("stock_dividends")
