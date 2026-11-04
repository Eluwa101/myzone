from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str


class PendingActionOut(BaseModel):
    id: UUID
    tool_name: str
    description: str
    payload: dict
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatResponse(BaseModel):
    reply: str
    pending_actions: list[PendingActionOut] = []


class AgentActionOut(BaseModel):
    id: UUID
    tool_name: str
    payload: dict
    result: dict
    created_at: datetime

    model_config = {"from_attributes": True}
