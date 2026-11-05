from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    thread_id: str | None = None
    image_data_url: str | None = None


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


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    answer: str


class ChatThreadOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    role: str
    content: str
    has_image: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class AgentActionOut(BaseModel):
    id: UUID
    tool_name: str
    payload: dict
    result: dict
    created_at: datetime

    model_config = {"from_attributes": True}
