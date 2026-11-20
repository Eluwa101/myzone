"""
A customer's lifetime activity timeline.

Two sources, merged newest-first at read time:

1. Rows that already exist for their own reasons - emails (OutboundMessage),
   orders, transactions, notes, scans, form submissions, and the customer's
   own created / unsubscribed timestamps. Never copied, so they can't drift.
2. customer_events - what would otherwise leave no trace: profile and status
   changes, merges, order/transaction edits and deletes, WhatsApp chats
   opened. The mutating controllers call record() / diff helpers below
   inside the same transaction as the change itself.

WhatsApp note: wa.me hands the message to the WhatsApp app, so the server can
only know a chat was *opened* with the text pre-filled, never that it was
actually sent. The log says exactly that.
"""
import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.custom_form import CustomForm, FormSubmission
from app.models.customer import Customer
from app.models.customer_event import CustomerEvent
from app.models.document_scan import DocumentScan
from app.models.org_note import OrgNote
from app.models.outbound_message import MessageChannel, MessageStatus, OutboundMessage
from app.schemas.activity import ActivityItem

MAX_PAGE_SIZE = 100
CUSTOMER_FIELDS = [
    "name", "phone", "email", "job", "nationality", "pet", "birthday", "address", "notes", "interests", "status",
    "consent_date",
]
ORDER_FIELDS = ["order_date", "delivery_date", "items", "amount", "currency", "paid", "delivered", "notes"]
TRANSACTION_FIELDS = ["date", "items", "amount", "currency"]

_LABELS = {
    "order_date": "order date", "delivery_date": "delivery date", "consent_date": "consent date",
    "first_name": "first name", "last_name": "last name",
}


# --- recording ----------------------------------------------------------------


def _plain(value):
    """JSON/comparison-friendly: enums to their value, dates to ISO, Decimals to floats."""
    if value is None:
        return None
    if hasattr(value, "value"):
        return value.value
    if isinstance(value, (datetime.date, datetime.datetime)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def snapshot(obj, fields: list[str]) -> dict:
    return {f: _plain(getattr(obj, f, None)) for f in fields}


def _short(value, length: int = 60) -> str:
    if value is None or value == "":
        return "(blank)"
    if isinstance(value, list):  # line items
        parts = [str(i.get("item") or i.get("name") or "?") + (f" x{i['qty']:g}" if i.get("qty") not in (None, 1, 1.0) else "") for i in value if isinstance(i, dict)]
        value = ", ".join(parts) or "(no items)"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    text = str(value)
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def diff(before: dict, after: dict) -> list[dict]:
    return [{"field": f, "from": before[f], "to": after.get(f)} for f in before if before[f] != after.get(f)]


def extra_diff(before: dict | None, after: dict | None) -> list[dict]:
    before, after = before or {}, after or {}
    return [
        {"field": f"extra.{k}", "from": before.get(k), "to": after.get(k)}
        for k in sorted(set(before) | set(after))
        if before.get(k) != after.get(k)
    ]


def describe_changes(changes: list[dict]) -> str:
    bits = []
    for c in changes:
        label = _LABELS.get(c["field"], c["field"].replace("extra.", "").replace("_", " "))
        if c["field"] in ("paid", "delivered") and c["to"] is True:
            bits.append(f"marked {label}")
        elif c["field"] in ("paid", "delivered"):
            bits.append(f"marked not {label}")
        else:
            bits.append(f"{label}: {_short(c['from'])} → {_short(c['to'])}")
    return "; ".join(bits)


def record(db: Session, org_id: UUID, customer_id: UUID, kind: str, summary: str, detail: str | None = None, data: dict | None = None) -> None:
    """Adds the event to the caller's open transaction - the caller commits, so
    the change and its history entry are saved (or rolled back) together."""
    db.add(CustomerEvent(org_id=org_id, customer_id=customer_id, kind=kind, summary=summary[:500], detail=detail, data=data or {}))


def record_changes(db: Session, org_id: UUID, customer_id: UUID, kind: str, noun: str, changes: list[dict]) -> None:
    if changes:
        record(db, org_id, customer_id, kind, f"{noun} updated", describe_changes(changes), {"changes": changes})


def record_whatsapp_opened(db: Session, org_id: UUID, customer_id: UUID, message: str) -> None:
    """A WhatsApp chat was opened with `message` pre-filled. Goes in the message
    log (channel whatsapp, status opened) - the same place emails live - so the
    Messages page and the Activity log show it without a second copy."""
    db.add(
        OutboundMessage(
            org_id=org_id, customer_id=customer_id, channel=MessageChannel.whatsapp, status=MessageStatus.opened,
            subject=None, body=(message or "").strip(),
        )
    )
    db.commit()


def move_history(db: Session, org_id: UUID, from_id: UUID, to_id: UUID) -> None:
    """When two customers are merged, everything that points at the one being
    removed is re-pointed at the survivor, so their history stays whole."""
    from sqlalchemy import select, update

    from app.models.org_note import note_customers

    for model in (CustomerEvent, OutboundMessage, FormSubmission):
        db.execute(update(model).where(model.customer_id == from_id).values(customer_id=to_id))
    db.execute(update(DocumentScan).where(DocumentScan.customer_id == from_id).values(customer_id=to_id))
    already = {r[0] for r in db.execute(select(note_customers.c.note_id).where(note_customers.c.customer_id == to_id))}
    for (note_id,) in db.execute(select(note_customers.c.note_id).where(note_customers.c.customer_id == from_id)).all():
        if note_id in already:
            db.execute(note_customers.delete().where(note_customers.c.note_id == note_id, note_customers.c.customer_id == from_id))
        else:
            db.execute(note_customers.update().where(note_customers.c.note_id == note_id, note_customers.c.customer_id == from_id).values(customer_id=to_id))


# --- reading ------------------------------------------------------------------


def _aware(dt: datetime.datetime | None) -> datetime.datetime:
    if dt is None:
        return datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
    return dt if dt.tzinfo else dt.replace(tzinfo=datetime.timezone.utc)


def _money(amount, currency) -> str:
    if amount is None:
        return ""
    return f"{float(amount):,.2f}" + (f" {currency}" if currency else "")


def _items_text(items: list, name_key: str) -> str:
    parts = []
    for i in items or []:
        qty = i.get("qty")
        parts.append(f"{i.get(name_key, '?')}" + (f" x{qty:g}" if isinstance(qty, (int, float)) and qty != 1 else ""))
    return ", ".join(parts) or "no items"


def build_timeline(db: Session, org_id: UUID, customer: Customer) -> list[ActivityItem]:
    cid = customer.id
    items: list[ActivityItem] = []

    items.append(ActivityItem(id=f"customer:{cid}", kind="customer_created", at=_aware(customer.created_at), title="Customer added", detail=f"ID {customer.display_id}"))
    if customer.email_unsubscribed_at:
        items.append(ActivityItem(id=f"unsub:{cid}", kind="unsubscribed", at=_aware(customer.email_unsubscribed_at), title="Unsubscribed from emails"))

    for m in db.query(OutboundMessage).filter(OutboundMessage.org_id == org_id, OutboundMessage.customer_id == cid).all():
        channel = m.channel.value
        label = {"email": "Email", "whatsapp": "WhatsApp", "sms": "SMS"}.get(channel, channel)
        if m.status == MessageStatus.opened:
            title, detail = f"{label} chat opened", " ".join((m.body or "").split())[:300] or None
        else:
            title = f"{label} {m.status.value}" + (f": {m.subject}" if m.subject else "")
            detail = m.error
        items.append(ActivityItem(id=f"msg:{m.id}", kind=channel, at=_aware(m.created_at), title=title, detail=detail, status=m.status.value, link=f"/messages/{m.id}"))

    for o in customer.orders:
        detail = _items_text(o.items, "name")
        extras = [x for x in (_money(o.amount, o.currency), f"due {o.delivery_date}" if o.delivery_date else "") if x]
        items.append(ActivityItem(id=f"order:{o.id}", kind="order_created", at=_aware(o.created_at), title=f"Order placed ({o.order_date})", detail=" · ".join([detail, *extras]), link=f"/customers/{cid}?tab=orders"))

    for t in customer.transactions:
        items.append(ActivityItem(
            id=f"tx:{t.id}", kind="transaction_added", at=_aware(t.created_at), title=f"Purchase recorded ({t.date})",
            detail=" · ".join([_items_text(t.items, "item"), _money(t.amount, t.currency)]), link=f"/customers/{cid}?tab=transactions",
        ))

    for n in db.query(OrgNote).filter(OrgNote.org_id == org_id, OrgNote.customers.any(Customer.id == cid)).all():
        who = " by the assistant" if n.created_by_agent else ""
        items.append(ActivityItem(id=f"note:{n.id}", kind="note_added", at=_aware(n.created_at), title=f"Note added{who}: {n.title}", detail=(n.content or "")[:300], link=f"/notes/{n.id}"))

    for s in db.query(DocumentScan).filter(DocumentScan.org_id == org_id, DocumentScan.customer_id == cid).all():
        items.append(ActivityItem(id=f"scan:{s.id}", kind="scan", at=_aware(s.created_at), title=f"Document scanned ({s.document_type or 'document'})", detail=s.summary, status=s.status, link="/scan"))

    forms = {f.id: f.name for f in db.query(CustomForm).filter(CustomForm.org_id == org_id).all()}
    for sub in db.query(FormSubmission).filter(FormSubmission.org_id == org_id, FormSubmission.customer_id == cid).all():
        items.append(ActivityItem(id=f"form:{sub.id}", kind="form_submission", at=_aware(sub.created_at), title=f"Submitted the form '{forms.get(sub.form_id, 'deleted form')}'"))

    for e in db.query(CustomerEvent).filter(CustomerEvent.org_id == org_id, CustomerEvent.customer_id == cid).all():
        items.append(ActivityItem(id=f"event:{e.id}", kind=e.kind, at=_aware(e.created_at), title=e.summary, detail=e.detail))

    items.sort(key=lambda i: (i.at, i.id), reverse=True)
    return items


def get_activity(db: Session, org_id: UUID, customer: Customer, page: int = 1, page_size: int = 30) -> tuple[list[ActivityItem], int]:
    timeline = build_timeline(db, org_id, customer)
    size = min(max(1, page_size), MAX_PAGE_SIZE)
    start = (max(1, page) - 1) * size
    return timeline[start : start + size], len(timeline)
