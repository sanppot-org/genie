"""Initial schema: Create price_data, candle_minute_1, and candle_daily tables

Revision ID: 001_initial
Revises:
Create Date: 2025-12-03 14:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create candle_minute_1 table (TimescaleDB hypertable)
    op.create_table(
        'candle_minute_1',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('localtime', sa.DateTime(), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.Column('timestamp', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('localtime', 'ticker'),  # TimescaleDB requirement
        sa.UniqueConstraint('localtime', 'ticker', name='uix_minute1_localtime_ticker')
    )
    op.create_index('idx_minute1_ticker_localtime', 'candle_minute_1', ['ticker', 'localtime'])
    op.create_index(op.f('ix_candle_minute_1_ticker'), 'candle_minute_1', ['ticker'])
    op.create_index(op.f('ix_candle_minute_1_timestamp'), 'candle_minute_1', ['timestamp'])

    # Create candle_daily table (TimescaleDB hypertable)
    op.create_table(
        'candle_daily',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('date', 'ticker'),  # TimescaleDB requirement
        sa.UniqueConstraint('date', 'ticker', name='uix_daily_date_ticker')
    )
    op.create_index('idx_daily_ticker_date', 'candle_daily', ['ticker', 'date'])
    op.create_index(op.f('ix_candle_daily_ticker'), 'candle_daily', ['ticker'])

    # Create sequences for id columns
    op.execute("CREATE SEQUENCE IF NOT EXISTS candle_minute_1_id_seq;")
    op.execute("CREATE SEQUENCE IF NOT EXISTS candle_daily_id_seq;")

    # Set id columns to use sequences (autoincrement)
    op.execute("ALTER TABLE candle_minute_1 ALTER COLUMN id SET DEFAULT nextval('candle_minute_1_id_seq');")
    op.execute("ALTER TABLE candle_daily ALTER COLUMN id SET DEFAULT nextval('candle_daily_id_seq');")

    # Set sequences to start at 1
    op.execute("SELECT setval('candle_minute_1_id_seq', 1, false);")
    op.execute("SELECT setval('candle_daily_id_seq', 1, false);")

    # Convert to TimescaleDB hypertables for time-series optimization
    op.execute(
        "SELECT create_hypertable('candle_minute_1', 'localtime', chunk_time_interval => INTERVAL '1 day', migrate_data => TRUE, if_not_exists => TRUE)")
    op.execute(
        "SELECT create_hypertable('candle_daily', 'date', chunk_time_interval => INTERVAL '1 year', migrate_data => TRUE, if_not_exists => TRUE)")


def downgrade() -> None:
    """Downgrade schema."""
    # Drop candle tables
    op.drop_index(op.f('ix_candle_minute_1_localtime'), table_name='candle_minute_1')
    op.drop_index(op.f('ix_candle_minute_1_timestamp'), table_name='candle_minute_1')
    op.drop_index(op.f('ix_candle_minute_1_ticker'), table_name='candle_minute_1')
    op.drop_index('idx_minute1_ticker_timestamp', table_name='candle_minute_1')
    op.drop_table('candle_minute_1')

    op.drop_index(op.f('ix_candle_daily_date'), table_name='candle_daily')
    op.drop_index(op.f('ix_candle_daily_ticker'), table_name='candle_daily')
    op.drop_index('idx_daily_ticker_date', table_name='candle_daily')
    op.drop_table('candle_daily')

    # Drop sequences
    op.execute("DROP SEQUENCE IF EXISTS candle_minute_1_id_seq;")
    op.execute("DROP SEQUENCE IF EXISTS candle_daily_id_seq;")
