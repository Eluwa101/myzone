"""add org_settings.default_country_code

Revision ID: a1b2c3d4e5f7
Revises: c95219934ac4
Create Date: 2026-11-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'c95219934ac4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('org_settings', sa.Column('default_country_code', sa.String(length=3), nullable=True))


def downgrade() -> None:
    op.drop_column('org_settings', 'default_country_code')
