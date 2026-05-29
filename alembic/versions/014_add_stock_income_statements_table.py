"""Add stock_income_statements table

Revision ID: 014_stock_income_statements
Revises: 013_tickers_sector_columns
Create Date: 2026-05-29

KIS 국내주식 손익계산서(finance/income-statement) — 결산기별 매출/영업이익/순이익.
period_type(ANNUAL/QUARTER) × stac_yymm(결산년월)별 1 row. 금액 단위 = 억원(Numeric).
분기는 KIS 원본(연단위 누적합산) 그대로 저장 — 단일분기 환산은 조회 레이어 파생.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "014_stock_income_statements"
down_revision: str | Sequence[str] | None = "013_tickers_sector_columns"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create stock_income_statements table."""
    op.create_table(
        "stock_income_statements",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("period_type", sa.String(length=8), nullable=False, comment="ANNUAL: 연간, QUARTER: 분기(누적)"),
        sa.Column("stac_yymm", sa.String(length=6), nullable=False, comment="결산년월 YYYYMM"),
        sa.Column("sale_account", sa.Numeric(precision=20, scale=2), nullable=True, comment="매출액(억원)"),
        sa.Column("sale_cost", sa.Numeric(precision=20, scale=2), nullable=True, comment="매출원가(억원)"),
        sa.Column("sale_totl_prfi", sa.Numeric(precision=20, scale=2), nullable=True, comment="매출총이익(억원)"),
        sa.Column("bsop_prti", sa.Numeric(precision=20, scale=2), nullable=True, comment="영업이익(억원)"),
        sa.Column("op_prfi", sa.Numeric(precision=20, scale=2), nullable=True, comment="경상이익(억원)"),
        sa.Column("thtr_ntin", sa.Numeric(precision=20, scale=2), nullable=True, comment="당기순이익(억원)"),
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
        sa.PrimaryKeyConstraint("ticker_id", "period_type", "stac_yymm"),
        sa.ForeignKeyConstraint(
            ["ticker_id"], ["tickers.id"], name="fk_stock_income_statements_ticker_id"
        ),
    )
    op.create_index(
        "ix_stock_income_statements_ticker_id_stac_yymm",
        "stock_income_statements",
        ["ticker_id", "stac_yymm"],
    )


def downgrade() -> None:
    """Drop stock_income_statements table."""
    op.drop_index(
        "ix_stock_income_statements_ticker_id_stac_yymm",
        table_name="stock_income_statements",
    )
    op.drop_table("stock_income_statements")
