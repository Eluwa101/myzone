"""lock down orders table with rls

Revision ID: f5c707ffc7e5
Revises: 8b94a11969bf
Create Date: 2026-11-05 00:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f5c707ffc7e5'
down_revision: Union[str, None] = '8b94a11969bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Same reasoning as e3469500b457: this table lives in `public`, so
    # Supabase's Data API would otherwise expose it to anon/authenticated.
    op.execute("ALTER TABLE orders ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE orders DISABLE ROW LEVEL SECURITY")
