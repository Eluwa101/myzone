"""transactions: replace single item/qty with an items list

Several line items recorded together in one checkout used to each become
their own Transaction row (one POST per line from the UI). This folds the
per-row item/qty into a JSON `items` list on the transaction, so multiple
items bought at once stay one transaction with one id. Existing rows become
single-item lists; `amount` already held each row's own total, so it is left
as-is (it now means "sum of this transaction's line amounts").

Revision ID: e2f3c244fa83
Revises: c3d4e5f6a7b8
Create Date: 2026-11-13 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e2f3c244fa83'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('transactions', sa.Column('items', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.execute(
        """
        UPDATE transactions
        SET items = jsonb_build_array(
            jsonb_build_object('item', item, 'qty', qty, 'amount', amount)
        )
        """
    )
    op.alter_column('transactions', 'items', nullable=False)
    op.drop_column('transactions', 'item')
    op.drop_column('transactions', 'qty')


def downgrade() -> None:
    op.add_column('transactions', sa.Column('item', sa.String(length=300), nullable=True))
    op.add_column('transactions', sa.Column('qty', sa.Numeric(12, 2), nullable=True))
    op.execute(
        """
        UPDATE transactions
        SET item = items->0->>'item',
            qty = (items->0->>'qty')::numeric
        """
    )
    op.alter_column('transactions', 'item', nullable=False)
    op.alter_column('transactions', 'qty', nullable=False, server_default='1')
    op.drop_column('transactions', 'items')
