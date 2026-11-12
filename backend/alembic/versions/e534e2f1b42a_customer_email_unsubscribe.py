"""add email_unsubscribed_at to customers

Revision ID: e534e2f1b42a
Revises: b81d69e3b829
Create Date: 2026-11-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e534e2f1b42a'
down_revision: Union[str, None] = 'b81d69e3b829'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('customers', sa.Column('email_unsubscribed_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('customers', 'email_unsubscribed_at')
