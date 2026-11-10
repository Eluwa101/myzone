"""auth: email verification, password reset tokens, Google sign-in

Revision ID: f1a2b3c4d5e6
Revises: e2f3c244fa83
Create Date: 2026-11-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e2f3c244fa83'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column('users', 'hashed_password', existing_type=sa.String(length=255), nullable=True)
    op.add_column('users', sa.Column('google_sub', sa.String(length=255), nullable=True))
    op.create_index('ix_users_google_sub', 'users', ['google_sub'], unique=True)
    op.add_column('users', sa.Column('email_verified', sa.Boolean(), nullable=True))
    # existing accounts predate this gate - don't lock anyone out retroactively
    op.execute("UPDATE users SET email_verified = true")
    op.alter_column('users', 'email_verified', nullable=False, server_default=sa.false())

    op.create_table(
        'auth_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('purpose', sa.Enum('verify_email', 'reset_password', name='authtokenpurpose'), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_auth_tokens_token_hash', 'auth_tokens', ['token_hash'], unique=True)
    op.execute("ALTER TABLE auth_tokens ENABLE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE auth_tokens DISABLE ROW LEVEL SECURITY")
    op.drop_index('ix_auth_tokens_token_hash', table_name='auth_tokens')
    op.drop_table('auth_tokens')
    op.execute("DROP TYPE IF EXISTS authtokenpurpose")

    op.drop_column('users', 'email_verified')
    op.drop_index('ix_users_google_sub', table_name='users')
    op.drop_column('users', 'google_sub')
    op.execute("UPDATE users SET hashed_password = '' WHERE hashed_password IS NULL")
    op.alter_column('users', 'hashed_password', existing_type=sa.String(length=255), nullable=False)
