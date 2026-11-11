from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class MergeTagOut(BaseModel):
    category: str
    category_label: str
    key: str
    label: str
    tag: str


class EmailTemplateCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    subject: str = Field(min_length=1, max_length=300)
    body_html: str = Field(min_length=1)


class EmailTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    subject: str | None = Field(default=None, min_length=1, max_length=300)
    body_html: str | None = Field(default=None, min_length=1)


class EmailTemplateOut(BaseModel):
    id: UUID
    name: str
    subject: str
    body_html: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class MessagePreviewRequest(BaseModel):
    customer_id: UUID
    subject: str = ""
    body_html: str


class MessagePreviewOut(BaseModel):
    subject: str
    body_html: str


class SendEmailRequest(BaseModel):
    customer_ids: list[UUID] = Field(min_length=1, max_length=500)
    subject: str = Field(min_length=1, max_length=300)
    body_html: str = Field(min_length=1)
    template_id: UUID | None = None
    skip_without_consent: bool = True


class SendEmailResult(BaseModel):
    queued: int
    skipped_no_email: int
    skipped_no_consent: int


class OutboundMessageOut(BaseModel):
    id: UUID
    customer_id: UUID
    channel: str
    status: str
    subject: str | None
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
