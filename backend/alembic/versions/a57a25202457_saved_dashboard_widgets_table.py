"""saved dashboard widgets table

Revision ID: a57a25202457
Revises: 75cca643257f
Create Date: 2026-11-05 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a57a25202457'
down_revision: Union[str, None] = '75cca643257f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('saved_dashboard_widgets',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('org_id', sa.Uuid(), nullable=False),
    sa.Column('user_id', sa.Uuid(), nullable=False),
    sa.Column('question', sa.Text(), nullable=False),
    sa.Column('title', sa.String(length=200), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_saved_dashboard_widgets_org_id'), 'saved_dashboard_widgets', ['org_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_saved_dashboard_widgets_org_id'), table_name='saved_dashboard_widgets')
    op.drop_table('saved_dashboard_widgets')
