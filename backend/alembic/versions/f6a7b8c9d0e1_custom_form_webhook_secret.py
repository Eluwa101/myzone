"""custom form webhook_secret (optional incoming-webhook signing)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-10 00:02:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('custom_forms', sa.Column('webhook_secret', sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column('custom_forms', 'webhook_secret')
