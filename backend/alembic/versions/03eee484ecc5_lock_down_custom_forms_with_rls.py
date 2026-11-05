"""lock down custom forms tables with rls

Revision ID: 03eee484ecc5
Revises: 82f9444a5707
Create Date: 2026-11-05 03:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '03eee484ecc5'
down_revision: Union[str, None] = '82f9444a5707'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = ["custom_forms", "form_submissions"]


def upgrade() -> None:
    # Same reasoning as e3469500b457: these tables live in `public`, so
    # Supabase's Data API would otherwise expose them to anon/authenticated.
    # Our own backend connects as the postgres role, which bypasses RLS, so
    # this doesn't affect the public form endpoints - only the side-channel
    # Supabase REST API.
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
