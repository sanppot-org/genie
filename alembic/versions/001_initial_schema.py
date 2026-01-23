"""Initial schema: Create candle_minute_1 hypertable and continuous aggregates (candle_hour_1, candle_daily)

Revision ID: 001_initial
Revises:
Create Date: 2025-12-03 14:40:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create trigger function for auto-updating updated_at
    op.execute("""
               CREATE OR REPLACE FUNCTION update_updated_at_column()
                   RETURNS TRIGGER AS
               $$
               BEGIN
                   NEW.updated_at = NOW();
                   RETURN NEW;
               END;
               $$ LANGUAGE plpgsql;
               """)

    # Create candle_minute_1 table (TimescaleDB hypertable)
    op.create_table(
        'candle_minute_1',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column('local_time', postgresql.TIMESTAMP(precision=0), nullable=False),
        sa.Column('ticker_id', sa.BigInteger(), nullable=False),
        sa.Column('open', sa.Float(), nullable=False),
        sa.Column('high', sa.Float(), nullable=False),
        sa.Column('low', sa.Float(), nullable=False),
        sa.Column('close', sa.Float(), nullable=False),
        sa.Column('volume', sa.Float(), nullable=False),
        sa.Column('utc_time', postgresql.TIMESTAMP(precision=0), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', postgresql.TIMESTAMP, nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('local_time', 'ticker_id'),  # TimescaleDB requirement
    )

    # Create trigger for auto-updating updated_at
    op.execute("""
               CREATE TRIGGER trigger_candle_minute_1_updated_at
                   BEFORE UPDATE
                   ON candle_minute_1
                   FOR EACH ROW
               EXECUTE FUNCTION update_updated_at_column();
               """)

    # Convert to TimescaleDB hypertables for time-series optimization
    op.execute(
        "SELECT create_hypertable('candle_minute_1', 'local_time', chunk_time_interval => INTERVAL '1 day', migrate_data => TRUE, if_not_exists => TRUE)")

    # Create 1-hour candlestick Continuous Aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW candle_hour_1
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 hour', local_time) AS local_time,
            ticker_id,
            first(open, local_time) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, local_time) AS close,
            sum(volume) AS volume
        FROM candle_minute_1
        GROUP BY time_bucket('1 hour', local_time), ticker_id
        WITH NO DATA;
    """)

    # Create daily candlestick Continuous Aggregate
    op.execute("""
        CREATE MATERIALIZED VIEW candle_daily
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 day', local_time) AS local_time,
            ticker_id,
            first(open, local_time) AS open,
            max(high) AS high,
            min(low) AS low,
            last(close, local_time) AS close,
            sum(volume) AS volume
        FROM candle_minute_1
        GROUP BY time_bucket('1 day', local_time), ticker_id
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
