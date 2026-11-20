import datetime

from pydantic import BaseModel, Field


class ActivityItem(BaseModel):
    id: str
    # customer_created | email | whatsapp | sms | order_created | order_updated | order_deleted |
    # transaction_added | transaction_updated | transaction_deleted | note_added | scan |
    # form_submission | profile_updated | merged | unsubscribed
    kind: str
    at: datetime.datetime
    title: str
    detail: str | None = None
    # outcome for sends: sent | failed | skipped | opened
    status: str | None = None
    # in-app path to the thing itself, when there is one
    link: str | None = None


class ActivityOut(BaseModel):
    items: list[ActivityItem]
    total: int
    page: int
    page_size: int


class WhatsappOpenedRequest(BaseModel):
    # the text that was pre-filled into the chat - kept short, it is a log not an archive
    message: str = Field(default="", max_length=5000)
