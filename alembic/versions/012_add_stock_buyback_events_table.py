"""Add stock_buyback_events table

Revision ID: 012_stock_buyback_events
Revises: 011_stock_treasury_stocks
Create Date: 2026-05-18

DART `tsstkAqDecsn`/`tsstkDpDecsn` (자기주식 취득·처분 결정) 공시 이벤트.
점수표 "정기적 자사주 매입·소각 (최소 연 1회 이상)" 판정용.
PK는 (ticker_id, rcept_no) — DART 접수번호가 종목별 유일.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "012_stock_buyback_events"
down_revision: str | Sequence[str] | None = "011_stock_treasury_stocks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create stock_buyback_events table."""
    op.create_table(
        "stock_buyback_events",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("rcept_no", sa.String(length=14), nullable=False, comment="DART 접수번호"),
        sa.Column("event_type", sa.String(length=16), nullable=False, comment="ACQUISITION 취득결정 / DISPOSAL 처분결정"),
        sa.Column("resolution_date", sa.Date(), nullable=False, comment="이사회 결의일 (aq_dd / dp_dd)"),
        sa.Column("planned_shares", sa.BigInteger(), nullable=True, comment="예정 보통주 수량"),
        sa.Column("planned_amount", sa.BigInteger(), nullable=True, comment="예정 보통주 금액(원)"),
        sa.Column("period_start", sa.Date(), nullable=True, comment="취득/처분 예정 시작일"),
        sa.Column("period_end", sa.Date(), nullable=True, comment="취득/처분 예정 종료일"),
        sa.Column("purpose", sa.String(length=255), nullable=True, comment="aq_pp / dp_pp 취득·처분 목적(자유 텍스트)"),
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
            ["ticker_id"], ["tickers.id"], name="fk_stock_buyback_events_ticker_id"
        ),
    )
    op.create_index(
        "ix_stock_buyback_events_ticker_id_resolution_date",
        "stock_buyback_events",
        ["ticker_id", "resolution_date"],
    )


def downgrade() -> None:
    """Drop stock_buyback_events table."""
    op.drop_index(
        "ix_stock_buyback_events_ticker_id_resolution_date",
        table_name="stock_buyback_events",
    )
    op.drop_table("stock_buyback_events")
