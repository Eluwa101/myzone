import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

EVENT_TYPES = {
    "customer.created", "customer.updated", "customer.deleted",
    "order.created", "order.updated", "order.deleted",
    "transaction.created", "transaction.updated", "transaction.deleted",
    "note.created", "note.updated", "note.deleted",
}


def _check_event_types(value: list[str] | None) -> list[str] | None:
    if value is None:
        return value
    if not value:
        raise ValueError("Select at least one event type.")
    unknown = set(value) - EVENT_TYPES
    if unknown:
        raise ValueError(f"Unknown event type(s): {', '.join(sorted(unknown))}.")
    return value


def _check_url(value: str | None) -> str | None:
    if value is not None and not value.startswith(("http://", "https://")):
        raise ValueError("target_url must start with http:// or https://.")
    return value


class WebhookSubscriptionCreate(BaseModel):
    target_url: str = Field(min_length=1, max_length=2000)
    event_types: list[str]

    @field_validator("target_url")
    @classmethod
    def check_url(cls, value: str) -> str:
        return _check_url(value)

    @field_validator("event_types")
    @classmethod
    def check_event_types(cls, value: list[str]) -> list[str]:
        return _check_event_types(value)


class WebhookSubscriptionUpdate(BaseModel):
    target_url: str | None = Field(default=None, min_length=1, max_length=2000)
    event_types: list[str] | None = None
    is_active: bool | None = None
    regenerate_secret: bool = False

    @field_validator("target_url")
    @classmethod
    def check_url(cls, value: str | None) -> str | None:
        return _check_url(value)

    @field_validator("event_types")
    @classmethod
    def check_event_types(cls, value: list[str] | None) -> list[str] | None:
        return _check_event_types(value)


class WebhookSubscriptionOut(BaseModel):
    id: UUID
    target_url: str
    secret: str
    event_types: list[str]
    is_active: bool
    created_at: datetime.datetime
    updated_at: datetime.datetime

    model_config = {"from_attributes": True}


class WebhookDeliveryOut(BaseModel):
    id: UUID
    event_type: str
    status: str
    response_code: int | None
    attempt_count: int
    payload: dict
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
