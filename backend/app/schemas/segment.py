import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.customer import CustomerStatus


class SegmentFilters(BaseModel):
    """All set filters are AND-ed together. A segment is always resolved
    live against current data - nothing here is a snapshot."""

    status: CustomerStatus | None = None
    interest_contains: str | None = Field(default=None, max_length=200)
    has_consent: bool | None = None
    search: str | None = Field(default=None, max_length=200)
    # has at least one transaction dated within the last N days
    last_purchase_within_days: int | None = Field(default=None, ge=1)
    # no transaction within the last N days (or never purchased) - churn/win-back targeting
    last_purchase_over_days: int | None = Field(default=None, ge=1)
    min_transactions: int | None = Field(default=None, ge=1)


class SegmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    filters: SegmentFilters = Field(default_factory=SegmentFilters)


class SegmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    filters: SegmentFilters | None = None


class SegmentOut(BaseModel):
    id: UUID
    name: str
    filters: SegmentFilters
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class SegmentMemberOut(BaseModel):
    id: UUID
    name: str
    email: str | None
    phone: str | None
    status: CustomerStatus

    model_config = {"from_attributes": True}


class SegmentResult(BaseModel):
    total: int
    members: list[SegmentMemberOut]
