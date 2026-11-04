import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OrgSettings(Base):
    __tablename__ = "org_settings"

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), primary_key=True)
    biz_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    whatsapp_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    qr_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization = relationship("Organization", back_populates="settings")
