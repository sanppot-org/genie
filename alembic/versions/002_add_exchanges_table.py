"""Add exchanges table

Revision ID: 002_exchanges
Revises: 001_initial
Create Date: 2025-01-09 00:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

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
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uix_exchange_name'),
    )
    op.create_index(op.f('ix_exchanges_name'), 'exchanges', ['name'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_exchanges_name'), table_name='exchanges')
    op.drop_table('exchanges')
