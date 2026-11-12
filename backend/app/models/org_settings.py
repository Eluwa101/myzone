import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, Text, Uuid as UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class OrgSettings(Base):
    __tablename__ = "org_settings"

    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), primary_key=True)
    biz_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    whatsapp_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    qr_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    team_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    brand_color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    manager_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    staff_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    default_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    # reply-to address for outgoing account emails sent on this org's behalf
    # (verification, password reset, etc.) - lets the "From" display name
    # show the business while replies land in the shop's own inbox, without
    # needing them to verify a sending domain of their own
    support_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # the part before the @ in this org's own sending address for customer
    # messages (<sender_handle>@<platform sending domain>) - unique across
    # every org, generated from the business name the first time settings
    # are read. A sending identity only: nothing receives mail there, which
    # is why customer messages always carry a Reply-To.
    sender_handle: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)

    organization = relationship("Organization", back_populates="settings")
