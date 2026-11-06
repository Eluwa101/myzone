"""customer first_name / last_name

Revision ID: c7d8e9f0a1b2
Revises: b1a2c3d4e5f6
Create Date: 2026-11-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c7d8e9f0a1b2'
down_revision: Union[str, None] = 'b1a2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('first_name', sa.String(length=100), nullable=True))
    op.add_column('customers', sa.Column('last_name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('customers', 'last_name')
    op.drop_column('customers', 'first_name')
