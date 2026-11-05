from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.controllers import saved_widget_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.saved_widget import SavedWidgetCreate, SavedWidgetOut

router = APIRouter(prefix="/api/dashboard/widgets", tags=["dashboard-widgets"])


@router.get("", response_model=list[SavedWidgetOut])
def list_widgets(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return saved_widget_controller.list_widgets(db, current_user.org_id)


@router.post("", response_model=SavedWidgetOut, status_code=status.HTTP_201_CREATED)
def create_widget(data: SavedWidgetCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return saved_widget_controller.create_widget(db, current_user.org_id, current_user.id, data)


@router.delete("/{widget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_widget(widget_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        saved_widget_controller.delete_widget(db, current_user.org_id, widget_id)
    except saved_widget_controller.SavedWidgetNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Widget not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
