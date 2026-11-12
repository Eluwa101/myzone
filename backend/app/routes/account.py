import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.controllers import account_closure_controller as closure
from app.core.database import get_db
from app.core.security import get_session_user
from app.models.user import User

# A signed-in owner only - never an API key - can close or reopen an account.
router = APIRouter(prefix="/api/account", tags=["account"])


class ClosureStatus(BaseModel):
    business_name: str
    closing: bool
    requested_at: datetime.datetime | None
    scheduled_for: datetime.datetime | None
    requested_by: str | None
    grace_days: int


class ClosureRequest(BaseModel):
    # the business name, typed out, so it can't happen by accident
    confirm_name: str = Field(min_length=1, max_length=200)


@router.get("/closure", response_model=ClosureStatus)
def get_closure(db: Session = Depends(get_db), current_user: User = Depends(get_session_user)):
    return closure.status(db, current_user.org_id)


@router.post("/closure", response_model=ClosureStatus)
def request_closure(data: ClosureRequest, db: Session = Depends(get_db), current_user: User = Depends(get_session_user)):
    try:
        return closure.request_closure(db, current_user, data.confirm_name)
    except closure.NotOwnerError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an account owner can close the account.")
    except closure.WrongConfirmationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=f'Type the business name exactly - "{e.args[0]}" - to confirm.'
        )


@router.delete("/closure", response_model=ClosureStatus)
def cancel_closure(db: Session = Depends(get_db), current_user: User = Depends(get_session_user)):
    try:
        return closure.cancel_closure(db, current_user)
    except closure.NotOwnerError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only an account owner can cancel the closure.")
    except closure.NotClosingError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This account isn't being closed.")
