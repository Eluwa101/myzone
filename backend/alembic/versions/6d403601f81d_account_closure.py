"""add account closure fields to organizations

Revision ID: 6d403601f81d
Revises: e534e2f1b42a
Create Date: 2026-11-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '6d403601f81d'
down_revision: Union[str, None] = 'e534e2f1b42a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('closure_requested_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('organizations', sa.Column('closure_scheduled_for', sa.DateTime(timezone=True), nullable=True))
    # no foreign key on purpose: the users are deleted before the
    # organization row when the closure finally runs
    op.add_column('organizations', sa.Column('closure_requested_by', postgresql.UUID(as_uuid=True), nullable=True))


def downgrade() -> None:
    op.drop_column('organizations', 'closure_requested_by')
    op.drop_column('organizations', 'closure_scheduled_for')
    op.drop_column('organizations', 'closure_requested_at')
