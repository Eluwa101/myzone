from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    customer_ids: list[UUID] = Field(default_factory=list)


class NoteUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)
    customer_ids: list[UUID] | None = None
    is_pending_review: bool | None = None


class NoteCustomerSummary(BaseModel):
    id: UUID
    name: str

    model_config = {"from_attributes": True}


class NoteOut(BaseModel):
    id: UUID
    title: str
    content: str
    is_pending_review: bool
    created_by_agent: bool
    created_at: datetime
    updated_at: datetime
    customers: list[NoteCustomerSummary] = []

    model_config = {"from_attributes": True}
