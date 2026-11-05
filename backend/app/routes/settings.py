from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.controllers import settings_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.settings import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return settings_controller.get_settings(db, current_user.org_id)


@router.put("", response_model=SettingsOut)
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return settings_controller.update_settings(db, current_user.org_id, data)
