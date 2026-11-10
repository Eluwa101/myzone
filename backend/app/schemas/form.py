import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

# Only simple, string-valued fields are offered as "customer"/"transaction"
# /"order" form fields - birthday/consent_date/status/qty-as-number etc. need
# type coercion or enum validation that isn't worth the complexity for a
# public intake form; they stay editable in the app afterward like any
# record. "name" stays recognized for forms created before the
# first_name/last_name convention below - new forms use the split fields.
CUSTOMER_FIELD_KEYS = {"name", "first_name", "last_name", "phone", "email", "job", "nationality", "pet", "address", "notes", "interests"}
TRANSACTION_FIELD_KEYS = {"tx_date", "tx_item", "tx_qty", "tx_amount", "tx_currency"}
ORDER_FIELD_KEYS = {"order_date", "order_delivery_date", "order_item", "order_qty", "order_price", "order_currency"}

# Every form - whether it's meant for orders, transactions, or general
# customer data - always collects these four so a record can be identified
# and reached; only first_name is required, mirroring how "name" alone used
# to be the sole required field.
REQUIRED_CONTACT_KEYS = {"first_name", "last_name", "phone", "email"}

FieldCategory = Literal["customer", "transaction", "order", "custom"]


class FormFieldDef(BaseModel):
    key: str = Field(min_length=1, max_length=100)
    label: str = Field(min_length=1, max_length=200)
    type: Literal["text", "textarea", "tel", "email", "number", "date"] = "text"
    required: bool = False
    category: FieldCategory = "custom"


def _validate_fields(fields: list[FormFieldDef]) -> list[FormFieldDef]:
    customer_fields = {f.key: f for f in fields if f.category == "customer"}
    missing = REQUIRED_CONTACT_KEYS - customer_fields.keys()
    if missing:
        raise ValueError(f"Every form must include: {', '.join(sorted(missing))}.")
    if not customer_fields["first_name"].required:
        raise ValueError("The 'first_name' field must be required.")
    for f in fields:
        if f.category == "customer" and f.key not in CUSTOMER_FIELD_KEYS:
            raise ValueError(f"'{f.key}' is not a recognized customer field.")
        if f.category == "transaction" and f.key not in TRANSACTION_FIELD_KEYS:
            raise ValueError(f"'{f.key}' is not a recognized transaction field.")
        if f.category == "order" and f.key not in ORDER_FIELD_KEYS:
            raise ValueError(f"'{f.key}' is not a recognized order field.")
    return fields


class FormCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    fields: list[FormFieldDef]

    @field_validator("fields")
    @classmethod
    def check_fields(cls, fields: list[FormFieldDef]) -> list[FormFieldDef]:
        return _validate_fields(fields)


class FormUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    fields: list[FormFieldDef] | None = None
    is_active: bool | None = None
    regenerate_token: bool = False
    enable_signing: bool = False
    disable_signing: bool = False

    @field_validator("fields")
    @classmethod
    def check_fields(cls, fields: list[FormFieldDef] | None) -> list[FormFieldDef] | None:
        return _validate_fields(fields) if fields is not None else fields


class FormOut(BaseModel):
    id: UUID
    name: str
    public_token: str
    fields: list[FormFieldDef]
    is_active: bool
    webhook_secret: str | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class PublicFormOut(BaseModel):
    """What an unauthenticated visitor or integration can see - no org id,
    no internal ids, just enough to render/drive the form."""

    name: str
    fields: list[FormFieldDef]
    business_name: str | None = None

    model_config = {"from_attributes": True}


class FormSubmitResult(BaseModel):
    status: str
    customer_created: bool
    transaction_logged: bool
    order_logged: bool


class FormSubmissionOut(BaseModel):
    id: UUID
    customer_id: UUID | None
    customer_name: str | None
    raw_payload: dict
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
