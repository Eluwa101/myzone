from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.ask_data import ask_data
from app.agent.runner import run_chat
from app.controllers import agent_controller, chat_history_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.agent import (
    AskRequest,
    AskResponse,
    ChatMessageOut,
    ChatRequest,
    ChatResponse,
    ChatThreadOut,
    PendingActionOut,
)

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
def chat(data: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    thread_id = data.thread_id or "default"
    chat_history_controller.record_user_message(
        db, current_user.org_id, current_user.id, thread_id, data.message, has_image=bool(data.image_data_url)
    )
    reply, pending = run_chat(db, current_user.org_id, current_user.id, data.message, thread_id, data.image_data_url)
    chat_history_controller.record_assistant_message(db, thread_id, reply)
    return ChatResponse(reply=reply, pending_actions=[PendingActionOut.model_validate(p) for p in pending])


@router.get("/threads", response_model=list[ChatThreadOut])
def list_threads(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return chat_history_controller.list_threads(db, current_user.org_id, current_user.id)


@router.get("/threads/{thread_id}/messages", response_model=list[ChatMessageOut])
def get_thread_messages(thread_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return chat_history_controller.get_thread_messages(db, current_user.org_id, current_user.id, thread_id)
    except chat_history_controller.ThreadNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such chat thread.")


@router.delete("/threads/{thread_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_thread(thread_id: str, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        chat_history_controller.delete_thread(db, current_user.org_id, current_user.id, thread_id)
    except chat_history_controller.ThreadNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such chat thread.")


@router.post("/ask", response_model=AskResponse)
def ask(data: AskRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    answer = ask_data(db, current_user.org_id, data.question)
    return AskResponse(answer=answer)


@router.get("/pending", response_model=list[PendingActionOut])
def list_pending(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return agent_controller.list_pending_actions(db, current_user.org_id)


@router.post("/pending/{action_id}/confirm")
def confirm_pending(action_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return agent_controller.confirm_pending_action(db, current_user.org_id, current_user.id, action_id)
    except agent_controller.PendingActionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such pending action.")
    except agent_controller.UnknownToolError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unrecognized pending action type.")


@router.post("/pending/{action_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
def reject_pending(action_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        agent_controller.reject_pending_action(db, current_user.org_id, action_id)
    except agent_controller.PendingActionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such pending action.")
