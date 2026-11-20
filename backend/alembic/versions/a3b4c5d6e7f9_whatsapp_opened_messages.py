"""whatsapp opens become message-log rows (status 'opened')

Revision ID: a3b4c5d6e7f9
Revises: a2b3c4d5e6f8
Create Date: 2026-11-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'a3b4c5d6e7f9'
down_revision: Union[str, None] = 'a2b3c4d5e6f8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # A new enum value can't be used in the transaction that adds it, so it
    # is committed on its own first.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE messagestatus ADD VALUE IF NOT EXISTS 'opened'")

    # WhatsApp chats opened so far were recorded as customer_events; move them
    # into the message log so the Messages page and the Activity log read one
    # source. (The old rows kept at most the first 500 characters of the text.)
    op.execute(
        """
        INSERT INTO outbound_messages (id, org_id, customer_id, channel, status, subject, body, created_at)
        SELECT id, org_id, customer_id, 'whatsapp', 'opened', NULL, COALESCE(detail, ''), created_at
        FROM customer_events
        WHERE kind = 'whatsapp_opened'
        """
    )
    op.execute("DELETE FROM customer_events WHERE kind = 'whatsapp_opened'")


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO customer_events (id, org_id, customer_id, kind, summary, detail, data, created_at)
        SELECT id, org_id, customer_id, 'whatsapp_opened', 'WhatsApp chat opened', NULLIF(body, ''), '{}', created_at
        FROM outbound_messages
        WHERE channel = 'whatsapp' AND status = 'opened'
        """
    )
    op.execute("DELETE FROM outbound_messages WHERE channel = 'whatsapp' AND status = 'opened'")
    # Postgres can't drop a single enum value; 'opened' stays defined but unused.
