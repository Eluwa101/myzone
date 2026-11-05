"""lock down org notes tables with rls

Revision ID: 75cca643257f
Revises: 5b1c3c6dda47
Create Date: 2026-11-05 01:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '75cca643257f'
down_revision: Union[str, None] = '5b1c3c6dda47'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = ["org_notes", "note_customers"]


def upgrade() -> None:
    # Same reasoning as e3469500b457: these tables live in `public`, so
    # Supabase's Data API would otherwise expose them to anon/authenticated.
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
