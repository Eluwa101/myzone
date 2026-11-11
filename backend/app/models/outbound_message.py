import datetime
import enum
import uuid

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MessageChannel(str, enum.Enum):
    email = "email"
    sms = "sms"
    whatsapp = "whatsapp"


class MessageStatus(str, enum.Enum):
    sent = "sent"
    failed = "failed"
    skipped = "skipped"


class OutboundMessage(Base):
    """Audit log of every customer-facing message send attempt - one row
    per recipient per batch, regardless of outcome, so a "sent to 12 of 14"
    summary can always be reconstructed and nothing sends twice silently."""

    __tablename__ = "outbound_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)
    template_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("email_templates.id"), nullable=True)

    channel: Mapped[MessageChannel] = mapped_column(Enum(MessageChannel))
    status: Mapped[MessageStatus] = mapped_column(Enum(MessageStatus))
    subject: Mapped[str | None] = mapped_column(String(300), nullable=True)
    body: Mapped[str] = mapped_column(Text)  # the resolved content actually sent (or attempted)
    provider_message_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
