"""Add adjusted price columns to stock_daily_candles

Revision ID: 017_adjusted_candle_columns
Revises: 016_stock_financial_ratios
Create Date: 2026-06-03

수정주가(액면분할·무상증자 소급 반영, 네이버 소스) 컬럼 추가.
원주가(open~close, KRX 원본)는 불변 보존하고 adj_* 컬럼을 별도로 둔다.
nullable ADD COLUMN이라 테이블 rewrite 없는 메타데이터 변경(잠금 최소).
백필 전 row는 NULL → 조회 시 원주가 폴백.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "017_adjusted_candle_columns"
down_revision: str | Sequence[str] | None = "016_stock_financial_ratios"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add nullable adj_* columns."""
    op.add_column("stock_daily_candles", sa.Column("adj_open", sa.Float(), nullable=True, comment="수정 시가"))
    op.add_column("stock_daily_candles", sa.Column("adj_high", sa.Float(), nullable=True, comment="수정 고가"))
    op.add_column("stock_daily_candles", sa.Column("adj_low", sa.Float(), nullable=True, comment="수정 저가"))
    op.add_column("stock_daily_candles", sa.Column("adj_close", sa.Float(), nullable=True, comment="수정 종가"))
    op.add_column(
        "stock_daily_candles",
        sa.Column("adj_volume", sa.BigInteger(), nullable=True, comment="수정 거래량(분할배수 반영)"),
    )


def downgrade() -> None:
    """Drop adj_* columns."""
    op.drop_column("stock_daily_candles", "adj_volume")
    op.drop_column("stock_daily_candles", "adj_close")
    op.drop_column("stock_daily_candles", "adj_low")
    op.drop_column("stock_daily_candles", "adj_high")
    op.drop_column("stock_daily_candles", "adj_open")
