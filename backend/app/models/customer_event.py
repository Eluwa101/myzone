import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, JSON, String, Text, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class CustomerEvent(Base):
    """Append-only history for things that leave no trace anywhere else: a
    profile edit, a status change, a merge, an order or transaction being
    edited or deleted, a WhatsApp chat being opened. Emails, order and
    transaction creation, notes, scans and form submissions are NOT copied
    here - the activity timeline reads those from their own tables
    (activity_controller.get_activity), so nothing is stored twice.

    Belongs to the customer: deleted with them, and moved to the surviving
    record when two customers are merged."""

    __tablename__ = "customer_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)

    # profile_updated | merged | order_updated | order_deleted | transaction_updated |
    # transaction_deleted
    # (WhatsApp opens live in outbound_messages, channel=whatsapp, status=opened)
    kind: Mapped[str] = mapped_column(String(40))
    summary: Mapped[str] = mapped_column(String(500))
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    data: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
