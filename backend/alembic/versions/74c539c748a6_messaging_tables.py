"""email templates and outbound message log

Revision ID: 74c539c748a6
Revises: fbb555728d66
Create Date: 2026-11-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '74c539c748a6'
down_revision: Union[str, None] = 'fbb555728d66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'email_templates',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('subject', sa.String(length=300), nullable=False),
        sa.Column('body_html', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("ALTER TABLE email_templates ENABLE ROW LEVEL SECURITY")

    op.create_table(
        'outbound_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id'), nullable=False, index=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('customers.id'), nullable=False, index=True),
        sa.Column('template_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('email_templates.id'), nullable=True),
        sa.Column('channel', sa.Enum('email', 'sms', 'whatsapp', name='messagechannel'), nullable=False),
        sa.Column('status', sa.Enum('sent', 'failed', 'skipped', name='messagestatus'), nullable=False),
        sa.Column('subject', sa.String(length=300), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('provider_message_id', sa.String(length=200), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute("ALTER TABLE outbound_messages ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE outbound_messages DISABLE ROW LEVEL SECURITY")
    op.drop_table('outbound_messages')
    op.execute("DROP TYPE IF EXISTS messagestatus")
    op.execute("DROP TYPE IF EXISTS messagechannel")

    op.execute("ALTER TABLE email_templates DISABLE ROW LEVEL SECURITY")
    op.drop_table('email_templates')
