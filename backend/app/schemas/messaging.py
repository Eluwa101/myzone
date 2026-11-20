from typing import Literal
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
    # merge tags that won't resolve (typos, unknown fields, unclosed blocks)
    problems: list[str] = []
    # fill-in-the-blanks like [discount] still in the text
    placeholders: list[str] = []


class MessagePreviewBatchRequest(BaseModel):
    # a page of recipients at a time - each one is resolved separately
    customer_ids: list[UUID] = Field(min_length=1, max_length=50)
    subject: str = ""
    body_html: str


class MessagePreviewBatchItem(BaseModel):
    customer_id: UUID
    subject: str
    body_html: str


class MessagePreviewBatchOut(BaseModel):
    previews: list[MessagePreviewBatchItem]
    # tag problems and [placeholders] are about the draft, not the recipient,
    # so they are reported once
    problems: list[str] = []
    placeholders: list[str] = []
    # ids that don't belong to this business (or no longer exist) - skipped, not an error
    missing: list[UUID] = []


class RewriteRequest(BaseModel):
    channel: Literal["email", "whatsapp"]
    action: Literal["shorten", "reformat", "friendlier", "rewrite"]
    # email: the HTML body (and subject); whatsapp: the plain text
    body: str = Field(min_length=1, max_length=100_000)
    subject: str | None = Field(default=None, max_length=500)
    instruction: str | None = Field(default=None, max_length=1000)
    # on: every merge tag comes back exactly as written (checked, not just requested)
    keep_merge_tags: bool = True


class RewriteOut(BaseModel):
    subject: str | None = None
    body: str
    # the original is being handed back because no safe rewrite came out
    unchanged: bool = False
    warning: str | None = None
    placeholders: list[str] = []


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
    skipped_unsubscribed: int = 0


class OutboundMessageOut(BaseModel):
    id: UUID
    customer_id: UUID
    customer_name: str | None = None
    channel: str
    status: str
    subject: str | None
    # first ~160 characters of the stored body, tags stripped (list + detail)
    body_preview: str = ""
    error: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class OutboundMessageDetailOut(OutboundMessageOut):
    # the full stored body - only on the single-message endpoint
    body: str | None = None


class SuggestedMergeTagOut(BaseModel):
    label: str
    tag: str
    reason: str


class EmailDraftRequest(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    segment_id: UUID | None = None
    format: Literal["simple", "designed"] = "simple"
    # when given, the assistant edits this email instead of starting over
    current_subject: str | None = Field(default=None, max_length=500)
    current_body: str | None = Field(default=None, max_length=100_000)


class WhatsappDraftRequest(BaseModel):
    description: str = Field(min_length=1, max_length=2000)
    segment_id: UUID | None = None
    # when given, the assistant edits this message instead of starting over
    current_text: str | None = Field(default=None, max_length=10_000)


class WhatsappDraftOut(BaseModel):
    text: str
    problems: list[str] = []
    placeholders: list[str] = []


class EmailDraftOut(BaseModel):
    subject: str
    body_html: str
    problems: list[str] = []
    placeholders: list[str] = []
