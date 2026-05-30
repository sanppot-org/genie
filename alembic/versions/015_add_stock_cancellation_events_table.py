"""Add stock_cancellation_events table

Revision ID: 015_stock_cancellation_events
Revises: 014_stock_income_statements
Create Date: 2026-05-30

DART 주식소각결정 공시(자사주 소각) — 종목별 (ticker_id, rcept_no) 1 row.
정기보고서가 아닌 수시공시 기반. 동일 접수번호 재호출은 UPSERT(정정공시 반영).
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "015_stock_cancellation_events"
down_revision: str | Sequence[str] | None = "014_stock_income_statements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create stock_cancellation_events table."""
    op.create_table(
        "stock_cancellation_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("rcept_no", sa.String(length=14), nullable=False, comment="DART 접수번호"),
        sa.Column("report_nm", sa.String(length=128), nullable=False, comment="공시명([기재정정]/(자회사) 판별·정정추적)"),
        sa.Column("resolution_date", sa.Date(), nullable=False, comment="이사회결의일(결정일)"),
        sa.Column("cancel_date", sa.Date(), nullable=True, comment="소각 예정일"),
        sa.Column("common_shares", sa.BigInteger(), nullable=True, comment="소각 보통주 수"),
        sa.Column("preferred_shares", sa.BigInteger(), nullable=True, comment="소각 종류주 수"),
        sa.Column("cancel_amount", sa.BigInteger(), nullable=True, comment="소각예정금액(원)"),
        sa.Column("acquisition_method", sa.String(length=64), nullable=True, comment="소각할 주식의 취득방법"),
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
        sa.PrimaryKeyConstraint("ticker_id", "rcept_no"),
        sa.ForeignKeyConstraint(
            ["ticker_id"], ["tickers.id"], name="fk_stock_cancellation_events_ticker_id"
        ),
    )
    op.create_index(
        "ix_stock_cancellation_events_ticker_id_resolution_date",
        "stock_cancellation_events",
        ["ticker_id", "resolution_date"],
    )


def downgrade() -> None:
    """Drop stock_cancellation_events table."""
    op.drop_index(
        "ix_stock_cancellation_events_ticker_id_resolution_date",
        table_name="stock_cancellation_events",
    )
    op.drop_table("stock_cancellation_events")
