from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.controllers import notification_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.notification import NotificationOut

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationOut])
def list_notifications(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return notification_controller.list_notifications(db, current_user.org_id)


@router.get("/unread-count")
def unread_count(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"count": notification_controller.unread_count(db, current_user.org_id)}


@router.post("/{notification_id}/read", response_model=NotificationOut)
def mark_read(notification_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return notification_controller.mark_read(db, current_user.org_id, notification_id)
    except notification_controller.NotificationNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found.")


@router.post("/read-all")
def mark_all_read(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"updated": notification_controller.mark_all_read(db, current_user.org_id)}
