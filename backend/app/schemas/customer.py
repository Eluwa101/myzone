from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.customer import CustomerStatus
from app.schemas.order import OrderOut
from app.schemas.transaction import TransactionOut


class CustomerBase(BaseModel):
    # Either `name` or (first_name/last_name) must be given - whichever
    # fields are present, `derive_name` below reconciles them into a single
    # `name` so dedup matching, search, CSV, and agent tools (all of which
    # key off `name`) keep working unchanged while first_name/last_name are
    # independently usable for personalization and segmentation.
    name: str | None = Field(default=None, max_length=200)
    first_name: str | None = Field(default=None, max_length=100)
    last_name: str | None = Field(default=None, max_length=100)
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
    @model_validator(mode="after")
    def derive_name(self) -> "CustomerCreate":
        combined = f"{self.first_name or ''} {self.last_name or ''}".strip()
        if combined:
            self.name = combined
        if not (self.name or "").strip():
            raise ValueError("Provide a name, or a first/last name.")
        return self


class CustomerUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    first_name: str | None = None
    last_name: str | None = None
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
    orders: list[OrderOut] = []

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


class ImportRequest(BaseModel):
    csv_text: str


class ImportResult(BaseModel):
    added: int
    merged: int
    skipped: int
    failed: int
    errors: list[str] = []
