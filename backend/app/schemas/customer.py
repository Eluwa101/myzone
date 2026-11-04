from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.customer import CustomerStatus
from app.schemas.transaction import TransactionOut


class CustomerBase(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=50)
    email: str | None = Field(default=None, max_length=255)
    job: str | None = Field(default=None, max_length=200)
    nationality: str | None = Field(default=None, max_length=100)
    pet: str | None = Field(default=None, max_length=200)
    birthday: date | None = None
    address: str | None = Field(default=None, max_length=300)
    notes: str | None = None
    interests: str | None = None
    status: CustomerStatus | None = None
    consent_date: date | None = None
    extra: dict[str, str] = Field(default_factory=dict)


class CustomerCreate(CustomerBase):
    pass


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    phone: str | None = None
    email: str | None = None
    job: str | None = None
    nationality: str | None = None
    pet: str | None = None
    birthday: date | None = None
    address: str | None = None
    notes: str | None = None
    interests: str | None = None
    status: CustomerStatus | None = None
    consent_date: date | None = None
    extra: dict[str, str] | None = None


class CustomerOut(CustomerBase):
    id: UUID
    org_id: UUID
    status: CustomerStatus
    status_auto: bool
    created_at: datetime
    updated_at: datetime
    transactions: list[TransactionOut] = []

    model_config = {"from_attributes": True}


class CustomerListOut(BaseModel):
    items: list[CustomerOut]
    total: int
    page: int
    page_size: int


class DuplicateMatch(BaseModel):
    existing: CustomerOut


class DuplicateGroup(BaseModel):
    keep: CustomerOut
    duplicates: list[CustomerOut]


class MergeRequest(BaseModel):
    keep_id: UUID
    merge_id: UUID


class ImportResult(BaseModel):
    added: int
    merged: int
    skipped: int
    failed: int
    errors: list[str] = []
