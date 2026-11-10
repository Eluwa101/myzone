import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class IdempotencyKey(Base):
    """Caches the response of a mutating request by (org, client-supplied
    key), so replaying the same offline-queued request twice - e.g. the
    client never heard back and retries it after reconnecting - returns the
    original result instead of creating or changing anything a second time."""

    __tablename__ = "idempotency_keys"
    __table_args__ = (UniqueConstraint("org_id", "key", name="uq_idempotency_org_key"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    key: Mapped[str] = mapped_column(String(200), index=True)
    method: Mapped[str] = mapped_column(String(10))
    path: Mapped[str] = mapped_column(String(500))
    status_code: Mapped[int] = mapped_column(Integer)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
