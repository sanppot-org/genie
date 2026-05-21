"""Add tickers sector/industry name columns

Revision ID: 013_tickers_sector_columns
Revises: 012_stock_buyback_events
Create Date: 2026-05-21

Adds KIS 주식기본조회 기반 업종/섹터 7개 컬럼:
- industry_name (KSIC 코드명)
- sector_(large|mid|small)_(code|name) 6개 (KIS 지수업종 3단)

기존 industry_code(KSIC 코드)는 그대로 재사용. 모두 nullable — 점진적 백필 전략에서
sync마다 NULL인 row만 KIS 호출하여 채운다.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "013_tickers_sector_columns"
down_revision: str | Sequence[str] | None = "012_stock_buyback_events"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add 7 sector/industry columns to tickers."""
    op.add_column("tickers", sa.Column("industry_name", sa.String(length=100), nullable=True))
    op.add_column("tickers", sa.Column("sector_large_code", sa.String(length=8), nullable=True))
    op.add_column("tickers", sa.Column("sector_large_name", sa.String(length=50), nullable=True))
    op.add_column("tickers", sa.Column("sector_mid_code", sa.String(length=8), nullable=True))
    op.add_column("tickers", sa.Column("sector_mid_name", sa.String(length=50), nullable=True))
    op.add_column("tickers", sa.Column("sector_small_code", sa.String(length=8), nullable=True))
    op.add_column("tickers", sa.Column("sector_small_name", sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Drop 7 sector/industry columns from tickers."""
    op.drop_column("tickers", "sector_small_name")
    op.drop_column("tickers", "sector_small_code")
    op.drop_column("tickers", "sector_mid_name")
    op.drop_column("tickers", "sector_mid_code")
    op.drop_column("tickers", "sector_large_name")
    op.drop_column("tickers", "sector_large_code")
    op.drop_column("tickers", "industry_name")
