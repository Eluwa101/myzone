"""add support_email to org_settings

Revision ID: 2bd24bd9d955
Revises: f1a2b3c4d5e6
Create Date: 2026-11-15 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2bd24bd9d955'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('org_settings', sa.Column('support_email', sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column('org_settings', 'support_email')
