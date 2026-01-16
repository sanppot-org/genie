"""Add exchanges table

Revision ID: 002_exchanges
Revises: 001_initial
Create Date: 2025-01-09 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002_exchanges'
down_revision: str | Sequence[str] | None = '001_initial'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create exchanges table
    op.create_table(
        'exchanges',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('timezone', sa.String(length=50), nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', postgresql.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uix_exchange_name'),
    )

    # Create trigger for auto-updating updated_at
    op.execute("""
               CREATE TRIGGER trigger_exchanges_updated_at
                   BEFORE UPDATE
                   ON exchanges
                   FOR EACH ROW
               EXECUTE FUNCTION update_updated_at_column();
               """)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('exchanges')
