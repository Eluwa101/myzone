"""Platform admin: list every business and open one to help its owner.

Who counts as an admin is the PLATFORM_ADMIN_EMAILS setting, not anything
stored in the database - so no one can make themselves an admin through
the app. Opening a business hands out a short-lived session for it (see
security.create_admin_session_token); the business is told in its bell,
and the switch plus every change made in it is logged permanently."""
import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.controllers import notification_controller
from app.core.database import get_db
from app.core.security import ADMIN_SESSION_HOURS, create_admin_session_token, get_current_user, home_org_id, is_platform_admin
from app.models.admin_access_log import AdminAccessLog
from app.models.customer import Customer
from app.models.org_settings import OrgSettings
from app.models.organization import Organization
from app.models.user import User, UserRole

router = APIRouter(prefix="/api/admin", tags=["admin"])


def get_platform_admin(current_user: User = Depends(get_current_user)) -> User:
    if not is_platform_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only MyShop admins can do this.")
    return current_user


class AdminOrgOut(BaseModel):
    id: UUID
    name: str
    owner_email: str | None
    customers: int
    created_at: datetime.datetime
    closing: bool
    is_home: bool


class ImpersonateRequest(BaseModel):
    org_id: UUID


class AdminSession(BaseModel):
    access_token: str
    org_id: UUID
    org_name: str
    expires_at: datetime.datetime


def _org_name(db: Session, org: Organization) -> str:
    org_settings = db.get(OrgSettings, org.id)
    return (org_settings.biz_name if org_settings else None) or org.name


@router.get("/orgs", response_model=list[AdminOrgOut])
def list_orgs(db: Session = Depends(get_db), admin: User = Depends(get_platform_admin)):
    counts = dict(db.query(Customer.org_id, func.count(Customer.id)).group_by(Customer.org_id).all())
    owners: dict = {}
    for org_id, email in db.query(User.org_id, User.email).filter(User.role == UserRole.owner).order_by(User.created_at).all():
        owners.setdefault(org_id, email)
    home = home_org_id(db, admin)
    orgs = [
        AdminOrgOut(
            id=org.id,
            name=_org_name(db, org),
            owner_email=owners.get(org.id),
            customers=counts.get(org.id, 0),
            created_at=org.created_at,
            closing=org.closure_scheduled_for is not None,
            is_home=org.id == home,
        )
        for org in db.query(Organization).all()
    ]
    return sorted(orgs, key=lambda o: (not o.is_home, o.name.casefold()))


@router.post("/impersonate", response_model=AdminSession)
def impersonate(data: ImpersonateRequest, db: Session = Depends(get_db), admin: User = Depends(get_platform_admin)):
    org = db.get(Organization, data.org_id)
    if org is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such business.")
    if org.id == home_org_id(db, admin):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="That's your own business - use \"Back to my account\".")

    token, expires_at = create_admin_session_token(admin.id, org.id)
    db.add(AdminAccessLog(org_id=org.id, admin_user_id=admin.id, admin_email=admin.email, kind="switch"))
    db.commit()
    notification_controller.create_notification(
        db,
        org.id,
        "admin.access",
        "MyShop support opened your account to help",
        body=(
            f"A MyShop administrator signed in to your account at {datetime.datetime.now(datetime.timezone.utc):%d %b %Y, %H:%M} UTC "
            f"(access lasts up to {ADMIN_SESSION_HOURS} hours, and every change made is logged). "
            "Questions? Write to privacy@myshopp.cc."
        ),
    )
    return AdminSession(access_token=token, org_id=org.id, org_name=_org_name(db, org), expires_at=expires_at)


@router.post("/stop", status_code=status.HTTP_204_NO_CONTENT)
def stop(request: Request, db: Session = Depends(get_db), admin: User = Depends(get_platform_admin)):
    if getattr(request.state, "admin_session", False):
        db.add(AdminAccessLog(org_id=admin.org_id, admin_user_id=admin.id, admin_email=admin.email, kind="end"))
        db.commit()
