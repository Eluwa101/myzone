import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChatThread(Base):
    __tablename__ = "chat_threads"

    # the id is client-generated (crypto.randomUUID() in the browser) so the
    # frontend can address a thread before the first message round-trip;
    # it's still namespaced server-side by org_id/user_id on every query.
    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)

    title: Mapped[str] = mapped_column(String(200), default="New chat")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    messages = relationship("ChatMessage", back_populates="thread", cascade="all, delete-orphan", order_by="ChatMessage.created_at")
