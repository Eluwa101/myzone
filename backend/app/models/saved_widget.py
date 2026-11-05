import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SavedWidget(Base):
    __tablename__ = "saved_dashboard_widgets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"))

    question: Mapped[str] = mapped_column(Text)
    title: Mapped[str] = mapped_column(String(200))

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
