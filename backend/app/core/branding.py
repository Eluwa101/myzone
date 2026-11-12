from sqlalchemy.orm import Session

from app.core.email import sending_domain
from app.models.organization import Organization
from app.models.org_settings import OrgSettings
from app.models.user import User, UserRole


def branding_for(db: Session, org_id) -> tuple[str | None, str | None]:
    """(display_name, reply_to) for the platform's own account emails to
    this org's users (verification, password reset). These stay on the
    platform's address - they are MyShop talking to a MyShop user - with
    the business name in the display name. Falls back to (None, None) -
    the plain MyShop sender - if neither is set, which is always true
    right after signup (org_settings doesn't exist yet) but the org's own
    name still carries through as the fallback display name."""
    org = db.get(Organization, org_id)
    org_settings = db.get(OrgSettings, org_id)
    biz_name = (org_settings.biz_name if org_settings else None) or (org.name if org else None)
    display_name = f"{biz_name} via MyShop" if biz_name else None
    reply_to = org_settings.support_email if org_settings else None
    return display_name, reply_to


def customer_sender_for(db: Session, org_id) -> tuple[str | None, str, str | None]:
    """(display_name, from_address, reply_to) for messages this org sends
    to its own customers. Each org sends from its own address on the
    shared verified domain (<sender_handle>@<domain>), so recipients and
    spam filters see one consistent sender per business rather than every
    business sharing a single address.

    That address is a sending identity, not a mailbox - nothing receives
    mail there - so a Reply-To is always set when one can be found: the
    org's support email, else its owner's login email. Without that
    fallback a customer's reply would simply bounce."""
    from app.controllers import settings_controller

    org = db.get(Organization, org_id)
    org_settings = settings_controller.get_settings(db, org_id)
    display_name = org_settings.biz_name or (org.name if org else None)
    from_address = f"{org_settings.sender_handle}@{sending_domain()}"

    reply_to = org_settings.support_email
    if not reply_to:
        owner = (
            db.query(User)
            .filter(User.org_id == org_id, User.role == UserRole.owner)
            .order_by(User.created_at)
            .first()
        )
        reply_to = owner.email if owner else None
    return display_name, from_address, reply_to
