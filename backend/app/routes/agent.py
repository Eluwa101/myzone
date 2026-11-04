from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.agent.runner import run_chat
from app.controllers import agent_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.agent import ChatRequest, ChatResponse, PendingActionOut

router = APIRouter(prefix="/api/agent", tags=["agent"])


@router.post("/chat", response_model=ChatResponse)
def chat(data: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    reply, pending = run_chat(db, current_user.org_id, current_user.id, data.message)
    return ChatResponse(reply=reply, pending_actions=[PendingActionOut.model_validate(p) for p in pending])


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
