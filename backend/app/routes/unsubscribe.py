"""Public, unauthenticated unsubscribe endpoints - reached from the link in
an email's footer (via the web app's /unsubscribe page) or directly by a
mail app's one-click "Unsubscribe" button (RFC 8058 POST)."""
import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.controllers import notification_controller
from app.core.database import get_db
from app.core.unsubscribe import read_token
from app.models.customer import Customer
from app.models.org_settings import OrgSettings
from app.models.organization import Organization

router = APIRouter(prefix="/api/public/unsubscribe", tags=["unsubscribe"])


class UnsubscribeStatus(BaseModel):
    business_name: str
    unsubscribed: bool


def _customer(db: Session, token: str) -> Customer:
    customer_id = read_token(token)
    customer = db.get(Customer, customer_id) if customer_id else None
    if customer is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="This unsubscribe link isn't valid.")
    return customer


def _status(db: Session, customer: Customer) -> UnsubscribeStatus:
    org_settings = db.get(OrgSettings, customer.org_id)
    org = db.get(Organization, customer.org_id)
    name = (org_settings.biz_name if org_settings else None) or (org.name if org else "this business")
    return UnsubscribeStatus(business_name=name, unsubscribed=customer.email_unsubscribed_at is not None)


@router.get("/{token}", response_model=UnsubscribeStatus)
def get_status(token: str, db: Session = Depends(get_db)):
    return _status(db, _customer(db, token))


@router.post("/{token}", response_model=UnsubscribeStatus)
def unsubscribe(token: str, db: Session = Depends(get_db)):
    """Idempotent - mail apps may POST more than once. The body (RFC 8058's
    `List-Unsubscribe=One-Click`) is ignored."""
    customer = _customer(db, token)
    if customer.email_unsubscribed_at is None:
        customer.email_unsubscribed_at = datetime.datetime.now(datetime.timezone.utc)
        db.commit()
        notification_controller.create_notification(
            db, customer.org_id, "customer.unsubscribed", f"{customer.name} unsubscribed from your emails", link=f"/customers/{customer.id}"
        )
    return _status(db, customer)


@router.post("/{token}/resubscribe", response_model=UnsubscribeStatus)
def resubscribe(token: str, db: Session = Depends(get_db)):
    """Only the customer can undo it, from their own link - the business
    has no way to re-add someone who opted out."""
    customer = _customer(db, token)
    if customer.email_unsubscribed_at is not None:
        customer.email_unsubscribed_at = None
        db.commit()
        notification_controller.create_notification(
            db, customer.org_id, "customer.resubscribed", f"{customer.name} resubscribed to your emails", link=f"/customers/{customer.id}"
        )
    return _status(db, customer)
