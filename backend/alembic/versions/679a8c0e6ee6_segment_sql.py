"""add sql to segments (custom SQL segments)

Revision ID: 679a8c0e6ee6
Revises: 9c41e7a2b5d3
Create Date: 2026-11-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '679a8c0e6ee6'
down_revision: Union[str, None] = '9c41e7a2b5d3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('segments', sa.Column('sql', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('segments', 'sql')
