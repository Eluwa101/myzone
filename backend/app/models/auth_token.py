import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AuthTokenPurpose(str, enum.Enum):
    verify_email = "verify_email"
    reset_password = "reset_password"


class AuthToken(Base):
    """A one-time, expiring token sent by email (verification link, password
    reset link). Only a SHA-256 hash of the token is stored - the raw value
    exists only in the emailed link, so a DB read alone can never produce a
    usable token."""

    __tablename__ = "auth_tokens"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    purpose: Mapped[AuthTokenPurpose] = mapped_column(Enum(AuthTokenPurpose))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime.datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
