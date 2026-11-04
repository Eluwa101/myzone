"""lock down data api with rls

Revision ID: e3469500b457
Revises: 10e026fb94be
Create Date: 2026-11-04 22:21:24.991540

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e3469500b457'
down_revision: Union[str, None] = '10e026fb94be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = ["organizations", "users", "customers", "transactions", "org_settings"]


def upgrade() -> None:
    # Supabase auto-exposes every table in `public` to PostgREST (the Data
    # API) for the anon/authenticated roles. This app never uses that API —
    # it only talks to Postgres directly as the `postgres` role, which
    # bypasses RLS. Enabling RLS with zero policies denies anon/authenticated
    # entirely while leaving this app's own access untouched.
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
