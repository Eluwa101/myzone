"""add org-scoped customer display_id (CR001, CR002, ...)

Revision ID: fbb555728d66
Revises: 2bd24bd9d955
Create Date: 2026-11-16 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fbb555728d66'
down_revision: Union[str, None] = '2bd24bd9d955'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('organizations', sa.Column('customer_seq', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('customers', sa.Column('display_id', sa.String(length=20), nullable=True))

    # backfill existing customers in creation order, per org, as CR001, CR002, ...
    op.execute(
        """
        UPDATE customers c
        SET display_id = 'CR' || LPAD(sub.rn::text, 3, '0')
        FROM (
            SELECT id, ROW_NUMBER() OVER (PARTITION BY org_id ORDER BY created_at) AS rn
            FROM customers
        ) sub
        WHERE c.id = sub.id
        """
    )
    op.execute(
        """
        UPDATE organizations o
        SET customer_seq = sub.cnt
        FROM (SELECT org_id, COUNT(*) AS cnt FROM customers GROUP BY org_id) sub
        WHERE o.id = sub.org_id
        """
    )

    op.alter_column('customers', 'display_id', nullable=False)
    op.create_index('ix_customers_org_display_id', 'customers', ['org_id', 'display_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_customers_org_display_id', table_name='customers')
    op.drop_column('customers', 'display_id')
    op.drop_column('organizations', 'customer_seq')
