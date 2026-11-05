"""custom forms and submissions tables

Revision ID: 82f9444a5707
Revises: c2b799b3ee14
Create Date: 2026-11-05 03:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '82f9444a5707'
down_revision: Union[str, None] = 'c2b799b3ee14'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('custom_forms',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('org_id', sa.Uuid(), nullable=False),
    sa.Column('name', sa.String(length=200), nullable=False),
    sa.Column('public_token', sa.String(length=64), nullable=False),
    sa.Column('fields', sa.JSON(), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('public_token')
    )
    op.create_index(op.f('ix_custom_forms_org_id'), 'custom_forms', ['org_id'], unique=False)
    op.create_index(op.f('ix_custom_forms_public_token'), 'custom_forms', ['public_token'], unique=True)
    op.create_table('form_submissions',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('form_id', sa.Uuid(), nullable=False),
    sa.Column('org_id', sa.Uuid(), nullable=False),
    sa.Column('customer_id', sa.Uuid(), nullable=True),
    sa.Column('raw_payload', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
    sa.ForeignKeyConstraint(['form_id'], ['custom_forms.id'], ),
    sa.ForeignKeyConstraint(['org_id'], ['organizations.id'], ),
    sa.ForeignKeyConstraint(['customer_id'], ['customers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_form_submissions_form_id'), 'form_submissions', ['form_id'], unique=False)
    op.create_index(op.f('ix_form_submissions_org_id'), 'form_submissions', ['org_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_form_submissions_org_id'), table_name='form_submissions')
    op.drop_index(op.f('ix_form_submissions_form_id'), table_name='form_submissions')
    op.drop_table('form_submissions')
    op.drop_index(op.f('ix_custom_forms_public_token'), table_name='custom_forms')
    op.drop_index(op.f('ix_custom_forms_org_id'), table_name='custom_forms')
    op.drop_table('custom_forms')
