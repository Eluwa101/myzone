import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AdminAccessLog(Base):
    """A permanent record of a platform admin opening a business's account
    ("switch"), every change they made while in it ("request"), and leaving
    ("end")."""

    __tablename__ = "admin_access_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    # no foreign key: the log must outlive the admin's own account
    admin_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    admin_email: Mapped[str] = mapped_column(String(255))
    kind: Mapped[str] = mapped_column(String(20))  # switch | request | end
    method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
