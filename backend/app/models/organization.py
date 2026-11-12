import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200))
    # highest customer display_id (CR001, CR002, ...) number assigned so
    # far in this org - see customer_controller._next_display_id
    customer_seq: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    # account closure (see account_closure_controller): while scheduled_for
    # is set the account is read-only, and on that date it's deleted
    closure_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_scheduled_for: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closure_requested_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    users = relationship("User", back_populates="organization", cascade="all, delete-orphan")
    customers = relationship("Customer", back_populates="organization", cascade="all, delete-orphan")
    settings = relationship("OrgSettings", back_populates="organization", uselist=False, cascade="all, delete-orphan")
