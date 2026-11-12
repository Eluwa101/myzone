"""add sender_handle to org_settings (per-org sending address)

Revision ID: 9c41e7a2b5d3
Revises: 74c539c748a6
Create Date: 2026-11-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9c41e7a2b5d3'
down_revision: Union[str, None] = '74c539c748a6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('org_settings', sa.Column('sender_handle', sa.String(length=64), nullable=True))
    op.create_index('ix_org_settings_sender_handle', 'org_settings', ['sender_handle'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_org_settings_sender_handle', table_name='org_settings')
    op.drop_column('org_settings', 'sender_handle')
