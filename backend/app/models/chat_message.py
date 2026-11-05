import datetime
import uuid

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    thread_id: Mapped[str] = mapped_column(String(64), ForeignKey("chat_threads.id"), index=True)

    role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    has_image: Mapped[bool] = mapped_column(default=False)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    thread = relationship("ChatThread", back_populates="messages")
