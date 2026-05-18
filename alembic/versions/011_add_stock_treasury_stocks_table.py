"""Add stock_treasury_stocks table

Revision ID: 011_stock_treasury_stocks
Revises: 010_drop_dividend_yield
Create Date: 2026-05-18

DART `stockTotqySttus`(주식의 총수 현황) 기반 자사주 보유 비율 시계열.
정기보고서(사업/반기/Q1/Q3) 기준 결산일별 1 row.
PK는 (ticker_id, stlm_dt) — 같은 결산일은 가장 최근 보고서로 덮어쓰기.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "011_stock_treasury_stocks"
down_revision: str | Sequence[str] | None = "010_drop_dividend_yield"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create stock_treasury_stocks table."""
    op.create_table(
        "stock_treasury_stocks",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("stlm_dt", sa.Date(), nullable=False, comment="결산일"),
        sa.Column("reprt_code", sa.String(length=5), nullable=False, comment="11011 사업/11012 반기/11013 Q1/11014 Q3"),
        sa.Column("issued_shares", sa.BigInteger(), nullable=False, comment="발행주식 총수 (보통주+우선주 합계)"),
        sa.Column("treasury_shares", sa.BigInteger(), nullable=False, comment="자기주식 수 (보통주+우선주 합계)"),
        sa.Column("treasury_ratio", sa.Float(), nullable=False, comment="자사주 보유 비율(%) = treasury_shares / issued_shares * 100"),
        sa.Column("rcept_no", sa.String(length=14), nullable=True, comment="DART 접수번호"),
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
        sa.PrimaryKeyConstraint("ticker_id", "stlm_dt"),
        sa.ForeignKeyConstraint(
            ["ticker_id"], ["tickers.id"], name="fk_stock_treasury_stocks_ticker_id"
        ),
    )
    op.create_index(
        "ix_stock_treasury_stocks_ticker_id_stlm_dt",
        "stock_treasury_stocks",
        ["ticker_id", "stlm_dt"],
    )


def downgrade() -> None:
    """Drop stock_treasury_stocks table."""
    op.drop_index("ix_stock_treasury_stocks_ticker_id_stlm_dt", table_name="stock_treasury_stocks")
    op.drop_table("stock_treasury_stocks")
