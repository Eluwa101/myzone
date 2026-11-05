from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class SavedWidgetCreate(BaseModel):
    question: str = Field(min_length=1)
    title: str | None = Field(default=None, max_length=200)


class SavedWidgetOut(BaseModel):
    id: UUID
    question: str
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}
