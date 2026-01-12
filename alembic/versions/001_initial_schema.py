"""Initial schema: Create candle_minute_1 hypertable and continuous aggregates (candle_hour_1, candle_daily)

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
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('kst_time', sa.DateTime(), nullable=False),
        sa.Column('ticker_id', sa.BigInteger(), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.Column('timestamp', postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('kst_time', 'ticker_id'),  # TimescaleDB requirement
    )

    # Create sequences for id columns
    op.execute("CREATE SEQUENCE IF NOT EXISTS candle_minute_1_id_seq;")

    # Set id columns to use sequences (autoincrement)
    op.execute("ALTER TABLE candle_minute_1 ALTER COLUMN id SET DEFAULT nextval('candle_minute_1_id_seq');")

    # Set sequences to start at 1
    op.execute("SELECT setval('candle_minute_1_id_seq', 1, false);")

    # Convert to TimescaleDB hypertables for time-series optimization
    op.execute(
        "SELECT create_hypertable('candle_minute_1', 'kst_time', chunk_time_interval => INTERVAL '1 day', migrate_data => TRUE, if_not_exists => TRUE)")

    # Create 1-hour candlestick Continuous Aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW candle_hour_1
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', kst_time) AS kst_time,
            ticker_id,
            first(open, kst_time) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, kst_time) AS close,
            sum(volume) AS volume
        FROM candle_minute_1
        GROUP BY time_bucket('1 hour', kst_time), ticker_id
        WITH NO DATA;
    """)

    # Create daily candlestick Continuous Aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW candle_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', kst_time) AS kst_time,
            ticker_id,
            first(open, kst_time) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, kst_time) AS close,
            sum(volume) AS volume
        FROM candle_minute_1
        GROUP BY time_bucket('1 day', kst_time), ticker_id
        WITH NO DATA;
    """)

    # Add refresh policy for 1-hour candlestick (refresh every hour)
    op.execute("""
        SELECT add_continuous_aggregate_policy('candle_hour_1',
            start_offset => INTERVAL '3 hours',
            end_offset => INTERVAL '1 hour',
            schedule_interval => INTERVAL '1 hour');
    """)

    # Add refresh policy for daily candlestick (refresh every day)
    op.execute("""
        SELECT add_continuous_aggregate_policy('candle_daily',
            start_offset => INTERVAL '3 days',
            end_offset => INTERVAL '1 day',
            schedule_interval => INTERVAL '1 day');
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove continuous aggregate policies first
    op.execute("SELECT remove_continuous_aggregate_policy('candle_hour_1', if_exists => true);")
    op.execute("SELECT remove_continuous_aggregate_policy('candle_daily', if_exists => true);")

    # Drop continuous aggregates
    op.execute("DROP MATERIALIZED VIEW IF EXISTS candle_hour_1;")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS candle_daily;")

    # Drop candle tables
    op.drop_table('candle_minute_1')

    # Drop sequences
    op.execute("DROP SEQUENCE IF EXISTS candle_minute_1_id_seq;")
