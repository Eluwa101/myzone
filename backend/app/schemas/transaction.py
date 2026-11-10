import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TransactionItem(BaseModel):
    item: str = Field(min_length=1, max_length=300)
    qty: float = Field(default=1, ge=0)
    amount: float = Field(ge=0)


class TransactionCreate(BaseModel):
    date: datetime.date
    items: list[TransactionItem] = Field(min_length=1)
    currency: str = Field(default="", max_length=3)


class TransactionUpdate(BaseModel):
    date: datetime.date | None = None
    items: list[TransactionItem] | None = Field(default=None, min_length=1)
    currency: str | None = Field(default=None, max_length=3)


class TransactionOut(BaseModel):
    id: UUID
    customer_id: UUID
    date: datetime.date
    items: list[TransactionItem]
    amount: float
    currency: str

    model_config = {"from_attributes": True}
