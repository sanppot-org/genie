"""Initial schema: Create price_data, candle_minute_1, and candle_daily tables

Revision ID: 001_initial
Revises:
Create Date: 2025-12-03 14:40:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create price_data table
    op.create_table(
        'price_data',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('symbol', sa.String(length=20), nullable=False),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('timestamp', 'symbol', 'source', name='uix_timestamp_symbol_source')
    )

    # Create indexes for price_data
    op.create_index('idx_symbol_source_timestamp', 'price_data', ['symbol', 'source', 'timestamp'])
    op.create_index(op.f('ix_price_data_symbol'), 'price_data', ['symbol'])
    op.create_index(op.f('ix_price_data_timestamp'), 'price_data', ['timestamp'])

    # Create candle_minute_1 table (TimescaleDB hypertable)
    op.create_table(
        'candle_minute_1',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('timestamp', 'ticker'),  # TimescaleDB requirement
        sa.UniqueConstraint('timestamp', 'ticker', name='uix_minute1_timestamp_ticker')
    )
    op.create_index('idx_minute1_ticker_timestamp', 'candle_minute_1', ['ticker', 'timestamp'])
    op.create_index(op.f('ix_candle_minute_1_ticker'), 'candle_minute_1', ['ticker'])
    op.create_index(op.f('ix_candle_minute_1_timestamp'), 'candle_minute_1', ['timestamp'])

    # Create candle_daily table (TimescaleDB hypertable)
    op.create_table(
        'candle_daily',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ticker', sa.String(length=20), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint('timestamp', 'ticker'),  # TimescaleDB requirement
        sa.UniqueConstraint('timestamp', 'ticker', name='uix_daily_timestamp_ticker')
    )
    op.create_index('idx_daily_ticker_timestamp', 'candle_daily', ['ticker', 'timestamp'])
    op.create_index(op.f('ix_candle_daily_ticker'), 'candle_daily', ['ticker'])
    op.create_index(op.f('ix_candle_daily_timestamp'), 'candle_daily', ['timestamp'])

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
    op.execute("SELECT create_hypertable('candle_minute_1', 'timestamp', chunk_time_interval => INTERVAL '1 day', migrate_data => TRUE, if_not_exists => TRUE)")
    op.execute("SELECT create_hypertable('candle_daily', 'timestamp', chunk_time_interval => INTERVAL '1 year', migrate_data => TRUE, if_not_exists => TRUE)")


def downgrade() -> None:
    """Downgrade schema."""
    # Drop candle tables
    op.drop_index(op.f('ix_candle_minute_1_timestamp'), table_name='candle_minute_1')
    op.drop_index(op.f('ix_candle_minute_1_ticker'), table_name='candle_minute_1')
    op.drop_index('idx_minute1_ticker_timestamp', table_name='candle_minute_1')
    op.drop_table('candle_minute_1')

    op.drop_index(op.f('ix_candle_daily_timestamp'), table_name='candle_daily')
    op.drop_index(op.f('ix_candle_daily_ticker'), table_name='candle_daily')
    op.drop_index('idx_daily_ticker_timestamp', table_name='candle_daily')
    op.drop_table('candle_daily')

    # Drop sequences
    op.execute("DROP SEQUENCE IF EXISTS candle_minute_1_id_seq;")
    op.execute("DROP SEQUENCE IF EXISTS candle_daily_id_seq;")

    # Drop price_data table
    op.drop_index(op.f('ix_price_data_timestamp'), table_name='price_data')
    op.drop_index(op.f('ix_price_data_symbol'), table_name='price_data')
    op.drop_index('idx_symbol_source_timestamp', table_name='price_data')
    op.drop_table('price_data')
