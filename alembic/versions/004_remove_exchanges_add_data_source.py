"""Remove exchanges table and add data_source to tickers

Revision ID: 004_data_source
Revises: 003_tickers
Create Date: 2025-01-20

This migration:
1. Adds data_source column to tickers table
2. Migrates data from exchanges.name to tickers.data_source
3. Removes exchange_id foreign key and column from tickers
4. Drops exchanges table

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "004_data_source"
down_revision: str | Sequence[str] | None = "003_tickers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Remove exchanges and add data_source to tickers."""
    # 1. Add data_source column to tickers (nullable initially for data migration)
    op.add_column(
        "tickers",
        sa.Column("data_source", sa.String(length=20), nullable=True),
    )

    # 2. Migrate data: copy exchanges.name to tickers.data_source
    op.execute("""
               UPDATE tickers t
               SET data_source = e.name FROM exchanges e
               WHERE t.exchange_id = e.id
               """)

    # 3. Set default value for any tickers without exchange (fallback to 'upbit')
    op.execute("""
               UPDATE tickers
               SET data_source = 'upbit'
               WHERE data_source IS NULL
               """)

    # 4. Make data_source NOT NULL after migration
    op.alter_column("tickers", "data_source", nullable=False)

    # 5. Create index on data_source
    op.create_index("ix_tickers_data_source", "tickers", ["data_source"])

    # 6. Drop foreign key constraint and index on exchange_id
    op.drop_constraint("fk_tickers_exchange_id", "tickers", type_="foreignkey")
    op.drop_index("ix_tickers_exchange_id", table_name="tickers")

    # 7. Drop exchange_id column from tickers
    op.drop_column("tickers", "exchange_id")

    # 8. Drop exchanges table (trigger is dropped automatically with table)
    op.drop_table("exchanges")


def downgrade() -> None:
    """Restore exchanges table and exchange_id in tickers."""
    # 1. Recreate exchanges table
    op.create_table(
        "exchanges",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("timezone", sa.String(length=50), nullable=False),
        sa.Column("created_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uix_exchange_name"),
    )

    # 2. Recreate trigger for exchanges
    op.execute("""
               CREATE TRIGGER trigger_exchanges_updated_at
                   BEFORE UPDATE
                   ON exchanges
                   FOR EACH ROW
                   EXECUTE FUNCTION update_updated_at_column();
               """)

    # 3. Insert unique data_source values into exchanges with timezone mapping
    op.execute("""
               INSERT INTO exchanges (name, timezone)
               SELECT DISTINCT data_source,
                               CASE data_source
                                   WHEN 'upbit' THEN 'Asia/Seoul'
                                   WHEN 'binance' THEN 'UTC'
                                   WHEN 'hantu' THEN 'America/New_York'
                                   ELSE 'UTC'
                                   END
               FROM tickers
               """)

    # 4. Add exchange_id column to tickers (nullable initially)
    op.add_column(
        "tickers",
        sa.Column("exchange_id", sa.Integer(), nullable=True),
    )

    # 5. Migrate data: set exchange_id from exchanges.name matching data_source
    op.execute("""
               UPDATE tickers t
               SET exchange_id = e.id FROM exchanges e
               WHERE t.data_source = e.name
               """)

    # 6. Make exchange_id NOT NULL
    op.alter_column("tickers", "exchange_id", nullable=False)

    # 7. Create index and foreign key on exchange_id
    op.create_index("ix_tickers_exchange_id", "tickers", ["exchange_id"])
    op.create_foreign_key(
        "fk_tickers_exchange_id",
        "tickers",
        "exchanges",
        ["exchange_id"],
        ["id"],
    )

    # 8. Drop data_source column and index
    op.drop_index("ix_tickers_data_source", table_name="tickers")
    op.drop_column("tickers", "data_source")
