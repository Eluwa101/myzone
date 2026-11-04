"""lock down agent tables with rls

Revision ID: 88c3def9f9a8
Revises: 228ea9de6f93
Create Date: 2026-11-04 22:39:14.373514

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '88c3def9f9a8'
down_revision: Union[str, None] = '228ea9de6f93'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = ["pending_actions", "agent_actions"]


def upgrade() -> None:
    # Same reasoning as e3469500b457: these tables live in `public`, so
    # Supabase's Data API would otherwise expose them to anon/authenticated.
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
