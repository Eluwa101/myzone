import logging
import threading
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.controllers import notification_controller
from app.core.branding import branding_for
from app.core.database import SessionLocal
from app.core.email import send_raw
from app.core.merge_tags import MergeTagContext, resolve_merge_tags
from app.models.customer import Customer
from app.models.email_template import EmailTemplate
from app.models.organization import Organization
from app.models.org_settings import OrgSettings
from app.models.outbound_message import MessageChannel, MessageStatus, OutboundMessage
from app.schemas.messaging import EmailTemplateCreate, EmailTemplateUpdate, SendEmailRequest, SendEmailResult

logger = logging.getLogger(__name__)


class EmailTemplateNotFoundError(Exception):
    pass


# --- templates --------------------------------------------------------------


def list_templates(db: Session, org_id: UUID) -> list[EmailTemplate]:
    return db.query(EmailTemplate).filter(EmailTemplate.org_id == org_id).order_by(EmailTemplate.name).all()


def get_template(db: Session, org_id: UUID, template_id: UUID) -> EmailTemplate:
    template = db.query(EmailTemplate).filter(EmailTemplate.org_id == org_id, EmailTemplate.id == template_id).first()
    if not template:
        raise EmailTemplateNotFoundError()
    return template


def create_template(db: Session, org_id: UUID, data: EmailTemplateCreate) -> EmailTemplate:
    template = EmailTemplate(org_id=org_id, name=data.name, subject=data.subject, body_html=data.body_html)
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def update_template(db: Session, org_id: UUID, template_id: UUID, data: EmailTemplateUpdate) -> EmailTemplate:
    template = get_template(db, org_id, template_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(template, field, value)
    db.commit()
    db.refresh(template)
    return template


def delete_template(db: Session, org_id: UUID, template_id: UUID) -> None:
    template = get_template(db, org_id, template_id)
    db.delete(template)
    db.commit()


# --- preview ------------------------------------------------------------


def _load_customer_for_merge(db: Session, org_id: UUID, customer_id: UUID) -> Customer | None:
    return (
        db.query(Customer)
        .options(joinedload(Customer.orders), joinedload(Customer.transactions))
        .filter(Customer.org_id == org_id, Customer.id == customer_id)
        .first()
    )


def preview(db: Session, org_id: UUID, customer_id: UUID, subject: str, body_html: str) -> tuple[str, str] | None:
    customer = _load_customer_for_merge(db, org_id, customer_id)
    if not customer:
        return None
    org = db.get(Organization, org_id)
    org_settings = db.get(OrgSettings, org_id)
    ctx = MergeTagContext(customer=customer, org=org, org_settings=org_settings)
    return resolve_merge_tags(subject, ctx), resolve_merge_tags(body_html, ctx)


# --- sending --------------------------------------------------------------


def send_email_batch(db: Session, org_id: UUID, data: SendEmailRequest) -> SendEmailResult:
    customers = db.query(Customer).filter(Customer.org_id == org_id, Customer.id.in_(data.customer_ids)).all()

    eligible_ids: list[UUID] = []
    skipped_no_email = 0
    skipped_no_consent = 0

    for c in customers:
        if not c.email:
            skipped_no_email += 1
            db.add(
                OutboundMessage(
                    org_id=org_id, customer_id=c.id, template_id=data.template_id, channel=MessageChannel.email,
                    status=MessageStatus.skipped, subject=data.subject, body="", error="No email on file",
                )
            )
            continue
        if data.skip_without_consent and not c.consent_date:
            skipped_no_consent += 1
            db.add(
                OutboundMessage(
                    org_id=org_id, customer_id=c.id, template_id=data.template_id, channel=MessageChannel.email,
                    status=MessageStatus.skipped, subject=data.subject, body="", error="No recorded consent",
                )
            )
            continue
        eligible_ids.append(c.id)

    db.commit()

    if eligible_ids:
        threading.Thread(
            target=_send_batch,
            args=(org_id, eligible_ids, data.subject, data.body_html, data.template_id),
            daemon=True,
        ).start()

    return SendEmailResult(queued=len(eligible_ids), skipped_no_email=skipped_no_email, skipped_no_consent=skipped_no_consent)


def _send_batch(org_id: UUID, customer_ids: list[UUID], subject: str, body_html: str, template_id: UUID | None) -> None:
    """Runs on its own thread with its own DB session (same pattern as
    webhook delivery) so a slow email provider never blocks the request
    that kicked off the send. Resolves merge tags per-recipient, sends,
    and logs the outcome - one notification summarizes the whole batch."""
    db = SessionLocal()
    sent = failed = 0
    try:
        org = db.get(Organization, org_id)
        org_settings = db.get(OrgSettings, org_id)
        from_name, reply_to = branding_for(db, org_id)

        for customer_id in customer_ids:
            customer = _load_customer_for_merge(db, org_id, customer_id)
            if not customer or not customer.email:
                continue
            ctx = MergeTagContext(customer=customer, org=org, org_settings=org_settings)
            resolved_subject = resolve_merge_tags(subject, ctx)
            resolved_body = resolve_merge_tags(body_html, ctx)
            try:
                message_id = send_raw(customer.email, resolved_subject, resolved_body, from_name=from_name, reply_to=reply_to)
                status_, error = MessageStatus.sent, None
                sent += 1
            except Exception as e:  # noqa: BLE001 - recorded per-recipient, loop must continue
                message_id, status_, error = None, MessageStatus.failed, str(e)
                failed += 1
            db.add(
                OutboundMessage(
                    org_id=org_id, customer_id=customer.id, template_id=template_id, channel=MessageChannel.email,
                    status=status_, subject=resolved_subject, body=resolved_body, provider_message_id=message_id, error=error,
                )
            )
            db.commit()

        total = sent + failed
        if total:
            notification_type = "message.email.sent" if not failed else "message.email.partial"
            title = f"Email sent to {sent} of {total} customer{'s' if total != 1 else ''}"
            if failed:
                title += f" - {failed} failed"
            notification_controller.create_notification(db, org_id, notification_type, title, link="/messages")
    except Exception:  # noqa: BLE001 - a batch-send problem must never crash the background thread
        logger.exception("Email batch send failed for org %s", org_id)
    finally:
        db.close()
