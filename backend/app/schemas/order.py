import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    qty: float = Field(default=1, ge=0)


class OrderCreate(BaseModel):
    order_date: datetime.date
    delivery_date: datetime.date | None = None
    items: list[OrderItem] = Field(default_factory=list)
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    paid: bool = False
    delivered: bool = False
    notes: str | None = None


class OrderUpdate(BaseModel):
    order_date: datetime.date | None = None
    delivery_date: datetime.date | None = None
    items: list[OrderItem] | None = None
    amount: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=3)
    paid: bool | None = None
    delivered: bool | None = None
    notes: str | None = None


class OrderOut(BaseModel):
    id: UUID
    customer_id: UUID
    order_date: datetime.date
    delivery_date: datetime.date | None
    items: list[OrderItem]
    amount: float | None
    currency: str | None
    paid: bool
    delivered: bool
    notes: str | None

    model_config = {"from_attributes": True}
