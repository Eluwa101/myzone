import datetime
import secrets
import uuid

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, String, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def generate_public_token() -> str:
    return secrets.token_urlsafe(16)


def generate_webhook_secret() -> str:
    return secrets.token_hex(32)


class CustomForm(Base):
    __tablename__ = "custom_forms"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)

    name: Mapped[str] = mapped_column(String(200))
    public_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, default=generate_public_token)
    fields: Mapped[list] = mapped_column(JSON, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # When set, /submit requires a valid X-Signature header (HMAC-SHA256 of
    # the raw request body with this secret) - opt-in, since many no-code
    # tools (Zapier, Make) can't easily sign requests.
    webhook_secret: Mapped[str | None] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class FormSubmission(Base):
    __tablename__ = "form_submissions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("custom_forms.id"), index=True)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id"), index=True)
    customer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=True)

    raw_payload: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer")

    @property
    def customer_name(self) -> str | None:
        return self.customer.name if self.customer else None
