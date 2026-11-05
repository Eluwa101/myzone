"""lock down segments table with rls

Revision ID: 952aeaaf35a4
Revises: 0113b4d9e66e
Create Date: 2026-11-05 04:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '952aeaaf35a4'
down_revision: Union[str, None] = '0113b4d9e66e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE segments ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE segments DISABLE ROW LEVEL SECURITY")
