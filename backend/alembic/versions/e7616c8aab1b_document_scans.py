"""add document_scans

Revision ID: e7616c8aab1b
Revises: 6d403601f81d
Create Date: 2026-11-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'e7616c8aab1b'
down_revision: Union[str, None] = '6d403601f81d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'document_scans',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('image_hash', sa.String(length=64), nullable=False),
        sa.Column('display_id', sa.String(length=20), nullable=True),
        sa.Column('customer_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('document_type', sa.String(length=50), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('extracted', sa.JSON(), nullable=False),
        sa.Column('actions', sa.JSON(), nullable=False),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['org_id'], ['organizations.id']),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_document_scans_org_id', 'document_scans', ['org_id'])
    op.create_index('ix_document_scans_image_hash', 'document_scans', ['image_hash'])
    # same as every other table: Supabase's public data API can't read it
    op.execute("ALTER TABLE document_scans ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE document_scans DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_document_scans_image_hash', table_name='document_scans')
    op.drop_index('ix_document_scans_org_id', table_name='document_scans')
    op.drop_table('document_scans')
