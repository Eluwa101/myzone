"""lock down chat tables with rls

Revision ID: 49ea7752e4ad
Revises: 6009a6115c45
Create Date: 2026-11-05 00:35:32.277926

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '49ea7752e4ad'
down_revision: Union[str, None] = '6009a6115c45'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TABLES = ["chat_threads", "chat_messages"]


def upgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
