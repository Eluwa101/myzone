import datetime
import uuid

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class DocumentScan(Base):
    """One photographed receipt / form / note, and what was done with it.
    The photo itself isn't kept - only what was read from it."""

    __tablename__ = "document_scans"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    # processing -> done | needs_review | failed
    status: Mapped[str] = mapped_column(String(20), default="processing")
    # sha256 of the image bytes - the same photo uploaded twice is ignored
    image_hash: Mapped[str] = mapped_column(String(64), index=True)
    display_id: Mapped[str | None] = mapped_column(String(20), nullable=True)
    # no foreign key: a customer can be deleted while their scans are kept
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted: Mapped[dict] = mapped_column(JSON, default=dict)
    actions: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
