import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.controllers import scan_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User

router = APIRouter(prefix="/api/scans", tags=["scans"])


class ScanRequest(BaseModel):
    # a data: URL, the same format the assistant chat takes photos in
    image_data_url: str = Field(min_length=20, max_length=12_000_000)
    # optional context from whoever's scanning, e.g. "this is from last week"
    hint: str | None = Field(default=None, max_length=500)


class ScanOut(BaseModel):
    id: UUID
    status: str
    display_id: str | None
    customer_id: UUID | None
    document_type: str | None
    summary: str | None
    actions: list[str]
    error: str | None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


@router.post("", response_model=ScanOut, status_code=status.HTTP_202_ACCEPTED)
def create_scan(data: ScanRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return scan_controller.start_scan(db, current_user.org_id, current_user.id, data.image_data_url, data.hint)
    except scan_controller.InvalidImageError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))


@router.get("", response_model=list[ScanOut])
def list_scans(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return scan_controller.list_scans(db, current_user.org_id)
