"""org profile fields for onboarding

Revision ID: b1a2c3d4e5f6
Revises: 952aeaaf35a4
Create Date: 2026-11-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1a2c3d4e5f6'
down_revision: Union[str, None] = '952aeaaf35a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('org_settings', sa.Column('industry', sa.String(length=100), nullable=True))
    op.add_column('org_settings', sa.Column('team_size', sa.Integer(), nullable=True))
    op.add_column('org_settings', sa.Column('phone', sa.String(length=50), nullable=True))
    op.add_column('org_settings', sa.Column('address', sa.String(length=300), nullable=True))
    op.add_column('org_settings', sa.Column('brand_color', sa.String(length=20), nullable=True))
    op.add_column('org_settings', sa.Column('manager_name', sa.String(length=200), nullable=True))
    op.add_column('org_settings', sa.Column('staff_names', sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column('org_settings', 'staff_names')
    op.drop_column('org_settings', 'manager_name')
    op.drop_column('org_settings', 'brand_color')
    op.drop_column('org_settings', 'address')
    op.drop_column('org_settings', 'phone')
    op.drop_column('org_settings', 'team_size')
    op.drop_column('org_settings', 'industry')
