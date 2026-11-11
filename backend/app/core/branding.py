from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.org_settings import OrgSettings


def branding_for(db: Session, org_id) -> tuple[str | None, str | None]:
    """(display_name, reply_to) for this org's outgoing email - used for
    both account emails (verification, password reset) and customer-facing
    messages. The "From" name shows the business (so it doesn't just say
    generic MyShop), and replies land in the shop's own inbox if they've
    set one. Falls back to (None, None) - the plain MyShop sender - if
    neither is set, which is always true right after signup (org_settings
    doesn't exist yet) but the org's own name still carries through as the
    fallback display name."""
    org = db.get(Organization, org_id)
    org_settings = db.get(OrgSettings, org_id)
    biz_name = (org_settings.biz_name if org_settings else None) or (org.name if org else None)
    display_name = f"{biz_name} via MyShop" if biz_name else None
    reply_to = org_settings.support_email if org_settings else None
    return display_name, reply_to
