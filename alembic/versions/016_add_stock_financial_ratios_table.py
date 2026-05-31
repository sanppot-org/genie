"""Add stock_financial_ratios table

Revision ID: 016_stock_financial_ratios
Revises: 015_stock_cancellation_events
Create Date: 2026-05-31

KIS 국내주식 재무비율(finance/financial-ratio) — 결산기별 ROE/성장률/부채비율 등.
stac_yymm(결산년월)별 1 row(연간만 수집). 값은 스케일 없는 % 또는 원(Float).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "016_stock_financial_ratios"
down_revision: str | Sequence[str] | None = "015_stock_cancellation_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create stock_financial_ratios table."""
    op.create_table(
        "stock_financial_ratios",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("stac_yymm", sa.String(length=6), nullable=False, comment="결산년월 YYYYMM"),
        sa.Column("roe", sa.Float(), nullable=True, comment="ROE(%)"),
        sa.Column("debt_ratio", sa.Float(), nullable=True, comment="부채비율(%)"),
        sa.Column("reserve_rate", sa.Float(), nullable=True, comment="유보비율(%)"),
        sa.Column("revenue_growth", sa.Float(), nullable=True, comment="매출액 증가율(%)"),
        sa.Column("op_growth", sa.Float(), nullable=True, comment="영업이익 증가율(%)"),
        sa.Column("net_growth", sa.Float(), nullable=True, comment="순이익 증가율(%)"),
        sa.Column("eps", sa.Float(), nullable=True, comment="EPS(원)"),
        sa.Column("bps", sa.Float(), nullable=True, comment="BPS(원)"),
        sa.Column("sps", sa.Float(), nullable=True, comment="주당매출액(원)"),
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
        sa.PrimaryKeyConstraint("ticker_id", "stac_yymm"),
        sa.ForeignKeyConstraint(
            ["ticker_id"], ["tickers.id"], name="fk_stock_financial_ratios_ticker_id"
        ),
    )
    op.create_index(
        "ix_stock_financial_ratios_ticker_id_stac_yymm",
        "stock_financial_ratios",
        ["ticker_id", "stac_yymm"],
    )


def downgrade() -> None:
    """Drop stock_financial_ratios table."""
    op.drop_index(
        "ix_stock_financial_ratios_ticker_id_stac_yymm",
        table_name="stock_financial_ratios",
    )
    op.drop_table("stock_financial_ratios")
