"""segments keep a stored member list (snapshots)

Revision ID: b4c5d6e7f8a0
Revises: a3b4c5d6e7f9
Create Date: 2026-11-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b4c5d6e7f8a0'
down_revision: Union[str, None] = 'a3b4c5d6e7f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # NULL = never run. Existing segments are given their first snapshot the first
    # time they are opened (it needs the app's own filter / SQL evaluation, which a
    # migration can't reuse).
    op.add_column('segments', sa.Column('refreshed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_table('segment_members',
    sa.Column('segment_id', sa.Uuid(), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.Column('added_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['segment_id'], ['segments.id'], ),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('segment_id', 'customer_id')
    )
    op.create_index(op.f('ix_segment_members_customer_id'), 'segment_members', ['customer_id'], unique=False)
    # Same reasoning as e3469500b457: this table lives in `public`, so Supabase's
    # Data API would otherwise expose it to anon/authenticated.
    op.execute("ALTER TABLE segment_members ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.drop_index(op.f('ix_segment_members_customer_id'), table_name='segment_members')
    op.drop_table('segment_members')
    op.drop_column('segments', 'refreshed_at')
