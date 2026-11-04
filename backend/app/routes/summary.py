from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.controllers import summary_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.summary import SummaryOut

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("", response_model=SummaryOut)
def get_summary(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return summary_controller.get_summary(db, current_user.org_id)
