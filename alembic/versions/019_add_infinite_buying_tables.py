"""Add infinite buying ledger tables

Revision ID: 019_infinite_buying
Revises: 018_ticker_exchange
Create Date: 2026-06-20

무한매수법 자체 원장 3개 테이블: 설정/포지션/주문.
신규 테이블 생성이라 기존 테이블 잠금 없음.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "019_infinite_buying"
down_revision: str | Sequence[str] | None = "018_ticker_exchange"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create infinite_buying_config / _position / _order tables."""
    op.create_table(
        "infinite_buying_config",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("division", sa.Integer(), server_default="40", nullable=False),
        sa.Column("base_gap", sa.Float(), nullable=False),
        sa.Column("allocation", sa.Float(), nullable=False),
        sa.Column("compounding", sa.String(length=8), server_default="half", nullable=False),
        sa.Column("sell_limit_pct", sa.Float(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], name="fk_infinite_buying_config_ticker_id"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker_id"),
    )
    op.create_index("ix_infinite_buying_config_ticker_id", "infinite_buying_config", ["ticker_id"])

    op.create_table(
        "infinite_buying_position",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker_id", sa.Integer(), nullable=False),
        sa.Column("cycle_no", sa.Integer(), nullable=False),
        sa.Column("holding_qty", sa.Integer(), server_default="0", nullable=False),
        sa.Column("cumulative_buy", sa.Float(), server_default="0", nullable=False),
        sa.Column("per_round_amount", sa.Float(), nullable=False),
        sa.Column("phase", sa.String(length=16), server_default="first_half", nullable=False),
        sa.Column("status", sa.String(length=8), server_default="active", nullable=False),
        sa.Column("realized_pnl", sa.Float(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ticker_id"], ["tickers.id"], name="fk_infinite_buying_position_ticker_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_infinite_buying_position_ticker_id", "infinite_buying_position", ["ticker_id"])
    op.create_index("ix_ib_position_ticker_cycle", "infinite_buying_position", ["ticker_id", "cycle_no"], unique=True)

    op.create_table(
        "infinite_buying_order",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("position_id", sa.Integer(), nullable=False),
        sa.Column("kis_order_no", sa.String(length=32), nullable=True),
        sa.Column("side", sa.String(length=4), nullable=False),
        sa.Column("order_kind", sa.String(length=24), nullable=False),
        sa.Column("order_division", sa.String(length=8), nullable=False),
        sa.Column("target_price", sa.Float(), nullable=False),
        sa.Column("qty", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=8), server_default="pending", nullable=False),
        sa.Column("filled_qty", sa.Integer(), server_default="0", nullable=False),
        sa.Column("filled_price", sa.Float(), nullable=True),
        sa.Column("trade_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["position_id"], ["infinite_buying_position.id"], name="fk_infinite_buying_order_position_id"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_infinite_buying_order_position_id", "infinite_buying_order", ["position_id"])


def downgrade() -> None:
    """Drop infinite buying tables."""
    op.drop_index("ix_infinite_buying_order_position_id", table_name="infinite_buying_order")
    op.drop_table("infinite_buying_order")
    op.drop_index("ix_ib_position_ticker_cycle", table_name="infinite_buying_position")
    op.drop_index("ix_infinite_buying_position_ticker_id", table_name="infinite_buying_position")
    op.drop_table("infinite_buying_position")
    op.drop_index("ix_infinite_buying_config_ticker_id", table_name="infinite_buying_config")
    op.drop_table("infinite_buying_config")
