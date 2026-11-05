"""lock down saved dashboard widgets with rls

Revision ID: c2b799b3ee14
Revises: a57a25202457
Create Date: 2026-11-05 02:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c2b799b3ee14'
down_revision: Union[str, None] = 'a57a25202457'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE saved_dashboard_widgets ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE saved_dashboard_widgets DISABLE ROW LEVEL SECURITY")
