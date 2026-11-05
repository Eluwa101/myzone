import datetime
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Table, Text, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

note_customers = Table(
    "note_customers",
    Base.metadata,
    Column("note_id", UUID(as_uuid=True), ForeignKey("org_notes.id"), primary_key=True),
    Column("customer_id", UUID(as_uuid=True), ForeignKey("customers.id"), primary_key=True),
)


class OrgNote(Base):
    __tablename__ = "org_notes"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)

    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    is_pending_review: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by_agent: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    customers = relationship("Customer", secondary=note_customers)
