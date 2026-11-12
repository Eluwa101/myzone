from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.controllers import settings_controller
from app.core.database import get_db
from app.core.email import sending_domain
from app.core.security import get_current_user
from app.models.org_settings import OrgSettings
from app.models.user import User
from app.schemas.settings import SettingsOut, SettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"])


def _out(settings: OrgSettings) -> SettingsOut:
    out = SettingsOut.model_validate(settings)
    out.sender_domain = sending_domain()
    return out


@router.get("", response_model=SettingsOut)
def get_settings(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _out(settings_controller.get_settings(db, current_user.org_id))


@router.put("", response_model=SettingsOut)
def update_settings(data: SettingsUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return _out(settings_controller.update_settings(db, current_user.org_id, data))
    except settings_controller.InvalidSenderHandleError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e))
