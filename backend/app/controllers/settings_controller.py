from uuid import UUID

from sqlalchemy.orm import Session

from app.models.org_settings import OrgSettings
from app.schemas.settings import SettingsUpdate


def get_settings(db: Session, org_id: UUID) -> OrgSettings:
    settings = db.get(OrgSettings, org_id)
    if not settings:
        settings = OrgSettings(org_id=org_id)
        db.add(settings)
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(db: Session, org_id: UUID, data: SettingsUpdate) -> OrgSettings:
    settings = get_settings(db, org_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings
