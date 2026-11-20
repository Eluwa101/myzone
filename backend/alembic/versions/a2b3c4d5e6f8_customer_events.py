"""customer events (activity history)

Revision ID: a2b3c4d5e6f8
Revises: a1b2c3d4e5f7
Create Date: 2026-11-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2b3c4d5e6f8'
down_revision: Union[str, None] = 'a1b2c3d4e5f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('customer_events',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('org_id', sa.Uuid(), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('kind', sa.String(length=40), nullable=False),
    sa.Column('summary', sa.String(length=500), nullable=False),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_customer_events_org_id'), 'customer_events', ['org_id'], unique=False)
    op.create_index(op.f('ix_customer_events_customer_id'), 'customer_events', ['customer_id'], unique=False)
    # Same reasoning as e3469500b457: this table lives in `public`, so
    # Supabase's Data API would otherwise expose it to anon/authenticated.
    # Only the backend (which connects as the table owner) ever reads it.
    op.execute("ALTER TABLE customer_events ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(op.f('ix_customer_events_customer_id'), table_name='customer_events')
    op.drop_index(op.f('ix_customer_events_org_id'), table_name='customer_events')
    op.drop_table('customer_events')
