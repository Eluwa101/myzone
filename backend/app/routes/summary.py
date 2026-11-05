from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.controllers import summary_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.summary import MonthTotal, SummaryOut, TopCustomer

router = APIRouter(prefix="/api/summary", tags=["summary"])


@router.get("", response_model=SummaryOut)
def get_summary(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return summary_controller.get_summary(db, current_user.org_id, start_date=start_date, end_date=end_date)


@router.get("/top-customers", response_model=list[TopCustomer])
def get_top_customers(
    start_date: date | None = None,
    end_date: date | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return summary_controller.get_full_top_customers(db, current_user.org_id, start_date=start_date, end_date=end_date, limit=limit)


@router.get("/monthly", response_model=list[MonthTotal])
def get_monthly(
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return summary_controller.get_full_months(db, current_user.org_id, start_date=start_date, end_date=end_date)
