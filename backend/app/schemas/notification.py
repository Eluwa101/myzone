import datetime
from uuid import UUID

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: UUID
    type: str
    title: str
    body: str | None
    link: str | None
    read: bool
    created_at: datetime.datetime

    model_config = {"from_attributes": True}
