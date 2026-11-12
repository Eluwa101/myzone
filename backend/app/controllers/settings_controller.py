import re
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.org_settings import OrgSettings
from app.schemas.settings import SettingsUpdate

HANDLE_MAX_LENGTH = 40
# local parts that are either the platform's own or conventionally mean
# something to mail systems - an org claiming one would be confusing at
# best and impersonation at worst
RESERVED_HANDLES = {
    "abuse", "admin", "administrator", "billing", "bounce", "bounces", "hello", "help", "info", "mail",
    "mailer-daemon", "myshop", "no-reply", "noreply", "notifications", "postmaster", "root", "security",
    "send", "support", "system", "webmaster",
}


class InvalidSenderHandleError(Exception):
    pass


def normalize_handle(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())[:HANDLE_MAX_LENGTH]


def _handle_taken(db: Session, handle: str, org_id: UUID) -> bool:
    return db.query(OrgSettings).filter(OrgSettings.sender_handle == handle, OrgSettings.org_id != org_id).first() is not None


def _generate_handle(db: Session, org_id: UUID, biz_name: str | None) -> str:
    org = db.get(Organization, org_id)
    base = normalize_handle(biz_name or (org.name if org else "") or "") or "shop"
    if base in RESERVED_HANDLES:
        base = f"{base}shop"
    handle, n = base, 2
    while _handle_taken(db, handle, org_id):
        suffix = str(n)
        handle, n = f"{base[: HANDLE_MAX_LENGTH - len(suffix)]}{suffix}", n + 1
    return handle


def get_settings(db: Session, org_id: UUID) -> OrgSettings:
    settings = db.get(OrgSettings, org_id)
    if not settings:
        settings = OrgSettings(org_id=org_id)
        db.add(settings)
    if not settings.sender_handle:
        settings.sender_handle = _generate_handle(db, org_id, settings.biz_name)
    if settings in db.new or settings in db.dirty:
        db.commit()
        db.refresh(settings)
    return settings


def update_settings(db: Session, org_id: UUID, data: SettingsUpdate) -> OrgSettings:
    settings = get_settings(db, org_id)
    updates = data.model_dump(exclude_unset=True)

    if "sender_handle" in updates:
        raw = updates.pop("sender_handle") or ""
        handle = normalize_handle(raw)
        if len(handle) < 3:
            raise InvalidSenderHandleError("Sending address must be at least 3 letters or numbers.")
        if handle in RESERVED_HANDLES:
            raise InvalidSenderHandleError("That sending address is reserved - please choose another.")
        if _handle_taken(db, handle, org_id):
            raise InvalidSenderHandleError("That sending address is already taken by another business.")
        settings.sender_handle = handle

    for field, value in updates.items():
        setattr(settings, field, value)
    db.commit()
    db.refresh(settings)
    return settings
