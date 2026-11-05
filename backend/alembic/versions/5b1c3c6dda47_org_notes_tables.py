"""org notes and note_customers tables

Revision ID: 5b1c3c6dda47
Revises: f5c707ffc7e5
Create Date: 2026-11-05 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5b1c3c6dda47'
down_revision: Union[str, None] = 'f5c707ffc7e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('org_notes',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('org_id', sa.Uuid(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('is_pending_review', sa.Boolean(), nullable=False),
    sa.Column('created_by_agent', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_org_notes_org_id'), 'org_notes', ['org_id'], unique=False)
    op.create_table('note_customers',
    sa.Column('note_id', sa.Uuid(), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['note_id'], ['org_notes.id'], ),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('note_id', 'customer_id')
    )


def downgrade() -> None:
    op.drop_table('note_customers')
    op.drop_index(op.f('ix_org_notes_org_id'), table_name='org_notes')
    op.drop_table('org_notes')
