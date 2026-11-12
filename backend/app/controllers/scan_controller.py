"""Scanning a photographed document into a customer's records, with no one
in the loop: find the customer ID (CR004) on the paper, then record
whatever else it says - sales, orders, contact details, other facts - and
leave a bell notification saying exactly what was done.

Because nobody reviews it, the rules lean safe:
- No readable customer ID, or one that doesn't exist -> nothing written.
- A name on the paper that doesn't match that customer -> nothing written
  (a misread "CR004" for "CR009" shouldn't put a sale on the wrong person).
- Existing profile details are never overwritten; disagreements go into
  the note instead.
- The same photo twice, or a sale/order that's already recorded, is skipped.
- Every write goes through the normal controllers, so webhooks, status
  updates and display rules all behave as if a person entered it."""
import base64
import binascii
import datetime
import hashlib
import logging
import re
import threading
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.agent.document_reader import DocumentReadError, read_document
from app.controllers import customer_controller, notification_controller, note_controller, order_controller, settings_controller, transaction_controller
from app.core.database import SessionLocal
from app.models.customer import Customer
from app.models.document_scan import DocumentScan
from app.schemas.customer import CustomerUpdate
from app.schemas.note import NoteCreate
from app.schemas.order import OrderCreate, OrderItem
from app.schemas.transaction import TransactionCreate, TransactionItem

logger = logging.getLogger(__name__)

MAX_IMAGE_BYTES = 8 * 1024 * 1024
_DATA_URL = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.+)$", re.DOTALL)
_PROFILE_FIELDS = ("first_name", "last_name", "phone", "email", "job", "nationality", "pet", "address", "interests", "birthday")
_NAME_STOPWORDS = {"mr", "mrs", "ms", "miss", "dr", "chief", "alhaji", "madam", "sir", "the"}


class InvalidImageError(Exception):
    pass


# --- starting a scan ----------------------------------------------------------


def _image_bytes(image_data_url: str) -> bytes:
    m = _DATA_URL.match(image_data_url or "")
    if not m:
        raise InvalidImageError("Upload a photo (JPEG, PNG or WebP).")
    try:
        data = base64.b64decode(m.group(2), validate=False)
    except (binascii.Error, ValueError) as e:
        raise InvalidImageError("That image couldn't be read.") from e
    if not data:
        raise InvalidImageError("That image is empty.")
    if len(data) > MAX_IMAGE_BYTES:
        raise InvalidImageError("That image is too large - keep it under 8 MB.")
    return data


def start_scan(db: Session, org_id: UUID, user_id: UUID, image_data_url: str, hint: str | None = None) -> DocumentScan:
    """Records the scan and reads it in the background. The same photo
    uploaded again returns the earlier scan instead of processing twice."""
    image_hash = hashlib.sha256(_image_bytes(image_data_url)).hexdigest()
    earlier = (
        db.query(DocumentScan)
        .filter(DocumentScan.org_id == org_id, DocumentScan.image_hash == image_hash, DocumentScan.status != "failed")
        .first()
    )
    if earlier:
        return earlier
    scan = DocumentScan(org_id=org_id, user_id=user_id, image_hash=image_hash, status="processing", extracted={}, actions=[])
    db.add(scan)
    db.commit()
    db.refresh(scan)
    _start_in_background(_process_in_background, scan.id, image_data_url, hint)
    return scan


def list_scans(db: Session, org_id: UUID, limit: int = 50) -> list[DocumentScan]:
    return db.query(DocumentScan).filter(DocumentScan.org_id == org_id).order_by(DocumentScan.created_at.desc()).limit(limit).all()


def _start_in_background(target, *args) -> None:
    """The test suite swaps this for an inline call."""
    threading.Thread(target=target, args=args, daemon=True).start()


def _process_in_background(scan_id: UUID, image_data_url: str, hint: str | None) -> None:
    db = SessionLocal()
    try:
        scan = db.get(DocumentScan, scan_id)
        if scan is None:
            return
        try:
            extracted = read_document(image_data_url, hint)
        except DocumentReadError as e:
            _finish(db, scan, "failed", error=str(e), title="Couldn't read a scanned document - try a clearer photo")
            return
        except Exception as e:  # noqa: BLE001 - the AI provider being down mustn't kill the thread silently
            logger.exception("Document scan %s: reading failed", scan_id)
            _finish(db, scan, "failed", error=f"The AI service didn't respond: {e}", title="Couldn't read a scanned document - please try again")
            return
        apply_extracted(db, scan, extracted)
    except Exception:  # noqa: BLE001
        logger.exception("Document scan %s failed", scan_id)
    finally:
        db.close()


# --- applying what was read -------------------------------------------------


def normalize_display_id(raw) -> list[str]:
    """Candidates for a written customer ID: "cr 4", "CR-004", "CR004" all
    find CR004."""
    if not raw:
        return []
    compact = re.sub(r"[\s\-_.#/]", "", str(raw)).upper()
    m = re.fullmatch(r"([A-Z]{1,4})0*(\d{1,8})", compact)
    if not m:
        return []
    letters, number = m.group(1), int(m.group(2))
    return list(dict.fromkeys([compact, f"{letters}{number:03d}", f"{letters}{number}"]))


def _name_tokens(name: str | None) -> set[str]:
    return {t for t in re.findall(r"[a-z]+", (name or "").casefold()) if len(t) >= 3 and t not in _NAME_STOPWORDS}


def names_match(on_document: str | None, customer: Customer) -> bool:
    """True unless the document names someone who clearly isn't this customer.
    Initials and partial names pass ("A. Obi", "Mrs Ada"); no name passes."""
    doc_tokens = _name_tokens(on_document)
    if not doc_tokens:
        return True
    return bool(doc_tokens & _name_tokens(f"{customer.name} {customer.first_name or ''} {customer.last_name or ''}"))


def _parse_date(value, fallback: datetime.date | None = None) -> datetime.date | None:
    if isinstance(value, str):
        try:
            return datetime.date.fromisoformat(value.strip()[:10])
        except ValueError:
            pass
    return fallback


def _number(value) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(re.sub(r"[^\d.\-]", "", str(value)))
    except ValueError:
        return None


def _money(amount: float, currency: str) -> str:
    return f"{currency + ' ' if currency else ''}{amount:,.2f}"


def _same_items(a: list[dict], b: list[dict], name_key: str) -> bool:
    return sorted((i.get(name_key) or "").casefold() for i in a) == sorted((i.get(name_key) or "").casefold() for i in b)


def _record_transactions(db, scan, customer, extracted, default_currency, actions) -> None:
    for tx in extracted.get("transactions") or []:
        if not isinstance(tx, dict):
            continue
        items = []
        for raw in tx.get("items") or []:
            amount = _number(raw.get("amount")) if isinstance(raw, dict) else None
            name = (str(raw.get("item") or "").strip() or "Purchase") if isinstance(raw, dict) else ""
            if amount is None or amount < 0 or not name:
                continue
            qty = _number(raw.get("qty")) or 1
            items.append({"item": name[:300], "qty": qty, "amount": amount})
        if not items:
            continue
        tx_date = _parse_date(tx.get("date"), _parse_date(extracted.get("date"), datetime.date.today()))
        currency = str(tx.get("currency") or extracted.get("currency") or default_currency or "").upper()[:3]
        total = sum(i["amount"] for i in items)
        duplicate = next(
            (
                t
                for t in customer.transactions
                if t.date == tx_date and abs(float(t.amount or 0) - total) < 0.005 and _same_items(t.items or [], items, "item")
            ),
            None,
        )
        if duplicate:
            actions.append(f"Skipped a sale on {tx_date.isoformat()} ({_money(total, currency)}) - already recorded")
            continue
        try:
            data = TransactionCreate(date=tx_date, currency=currency, items=[TransactionItem(**i) for i in items])
        except ValidationError:
            continue
        transaction_controller.add_transaction(db, scan.org_id, customer.id, data)
        names = ", ".join(i["item"] for i in items)
        actions.append(f"Recorded a sale on {tx_date.isoformat()}: {names} ({_money(total, currency)})")
        db.refresh(customer)


def _record_orders(db, scan, customer, extracted, default_currency, actions) -> None:
    for order in extracted.get("orders") or []:
        if not isinstance(order, dict):
            continue
        items = []
        for raw in order.get("items") or []:
            if not isinstance(raw, dict) or not str(raw.get("name") or "").strip():
                continue
            price = _number(raw.get("price"))
            items.append({"name": str(raw["name"]).strip()[:200], "qty": _number(raw.get("qty")) or 1, "price": price if price is None or price >= 0 else None})
        if not items:
            continue
        order_date = _parse_date(order.get("order_date"), _parse_date(extracted.get("date"), datetime.date.today()))
        amount = _number(order.get("amount"))
        currency = str(order.get("currency") or extracted.get("currency") or default_currency or "").upper()[:3]
        duplicate = next(
            (o for o in customer.orders if o.order_date == order_date and _same_items(o.items or [], items, "name")),
            None,
        )
        if duplicate:
            actions.append(f"Skipped an order on {order_date.isoformat()} - already recorded")
            continue
        try:
            data = OrderCreate(
                order_date=order_date,
                delivery_date=_parse_date(order.get("delivery_date")),
                items=[OrderItem(**i) for i in items],
                amount=amount if amount is not None and amount >= 0 else None,
                currency=currency or None,
                paid=bool(order.get("paid")),
                delivered=bool(order.get("delivered")),
            )
        except ValidationError:
            continue
        order_controller.create_order(db, scan.org_id, customer.id, data)
        names = ", ".join(i["name"] for i in items)
        actions.append(f"Recorded an order on {order_date.isoformat()}: {names}" + (f" ({_money(amount, currency)})" if amount else ""))
        db.refresh(customer)


def _update_profile(db, scan, customer, extracted, actions, conflicts) -> None:
    fields = extracted.get("customer_fields") if isinstance(extracted.get("customer_fields"), dict) else {}
    updates: dict = {}
    for field in _PROFILE_FIELDS:
        value = fields.get(field)
        if value in (None, "") or not str(value).strip():
            continue
        value = str(value).strip()
        if field == "birthday":
            parsed = _parse_date(value)
            if parsed is None:
                continue
            value = parsed
        current = getattr(customer, field)
        if current in (None, ""):
            updates[field] = value
        elif str(current).strip().casefold() != str(value).casefold():
            conflicts.append(f"{field.replace('_', ' ')}: the document says {value}, the profile has {current}")

    extras = extracted.get("custom_fields") if isinstance(extracted.get("custom_fields"), dict) else {}
    merged = dict(customer.extra or {})
    added_extra = []
    for label, value in extras.items():
        label, value = str(label).strip()[:100], str(value).strip() if value is not None else ""
        if not label or not value:
            continue
        existing_key = next((k for k in merged if k.casefold() == label.casefold()), None)
        if existing_key is None:
            merged[label] = value
            added_extra.append(label)
        elif str(merged[existing_key]).casefold() != value.casefold():
            conflicts.append(f"{existing_key}: the document says {value}, the profile has {merged[existing_key]}")
    if added_extra:
        updates["extra"] = merged

    if updates:
        try:
            customer_controller.update_customer(db, scan.org_id, customer.id, CustomerUpdate(**updates))
        except ValidationError:
            return
        labels = [f.replace("_", " ") for f in updates if f != "extra"] + added_extra
        actions.append(f"Added {', '.join(labels)} to the profile")


def _add_note(db, scan, customer, extracted, conflicts, actions) -> None:
    parts = []
    if extracted.get("notes"):
        parts.append(str(extracted["notes"]).strip())
    if conflicts:
        parts.append("Not changed on the profile - please check:\n" + "\n".join(f"- {c}" for c in conflicts))
    if not parts:
        return
    kind = (extracted.get("document_type") or "document").strip().lower()
    note_controller.create_note(
        db,
        scan.org_id,
        NoteCreate(title=f"From a scanned {kind}"[:200], content="\n\n".join(parts), customer_ids=[customer.id]),
        created_by_agent=True,
    )
    actions.append("Added a note with " + ("the rest of the document" if extracted.get("notes") else "details to check"))


def _finish(db: Session, scan: DocumentScan, status: str, *, title: str, error: str | None = None, link: str = "/scan") -> None:
    scan.status = status
    # a scan that wasn't recorded keeps its reason, for the Scan page
    scan.error = error or (title if status == "needs_review" else None)
    db.commit()
    if len(title) > 300:  # the notification title column's limit
        title = title[:299] + "…"
    notification_controller.create_notification(
        db, scan.org_id, f"scan.{status}", title, body="\n".join(scan.actions or []) or error, link=link
    )


def apply_extracted(db: Session, scan: DocumentScan, extracted: dict) -> DocumentScan:
    scan.extracted = extracted
    scan.document_type = (str(extracted.get("document_type") or "") or None) and str(extracted["document_type"])[:50]
    scan.summary = str(extracted.get("summary") or "")[:1000] or None
    candidates = normalize_display_id(extracted.get("customer_id"))
    scan.display_id = candidates[0] if candidates else None
    db.commit()

    if not candidates:
        _finish(db, scan, "needs_review", title="Scanned document has no customer ID - nothing was recorded")
        return scan

    customer = None
    for candidate in candidates:
        try:
            customer = customer_controller.get_customer_by_display_id(db, scan.org_id, candidate)
            break
        except customer_controller.CustomerNotFoundError:
            continue
    if customer is None:
        _finish(db, scan, "needs_review", title=f"No customer {scan.display_id} - the scanned document wasn't recorded")
        return scan

    scan.customer_id = customer.id
    scan.display_id = customer.display_id
    db.commit()
    if not names_match(extracted.get("customer_name"), customer):
        _finish(
            db,
            scan,
            "needs_review",
            title=f"Name on the scan ({extracted.get('customer_name')}) doesn't match {customer.display_id} ({customer.name}) - nothing was recorded",
            link=f"/customers/{customer.id}",
        )
        return scan

    default_currency = (settings_controller.get_settings(db, scan.org_id).default_currency or "").upper()
    actions: list[str] = []
    conflicts: list[str] = []
    _record_transactions(db, scan, customer, extracted, default_currency, actions)
    _record_orders(db, scan, customer, extracted, default_currency, actions)
    _update_profile(db, scan, customer, extracted, actions, conflicts)
    _add_note(db, scan, customer, extracted, conflicts, actions)

    scan.actions = actions or ["Nothing new to record - everything on it was already there"]
    kind = (scan.document_type or "document").lower()
    if not actions:
        headline = "nothing new"
    else:
        first = actions[0][0].lower() + actions[0][1:]
        headline = first + (f" (+{len(actions) - 1} more)" if len(actions) > 1 else "")
    _finish(db, scan, "done", title=f"Scanned {kind} for {customer.name} ({customer.display_id}): {headline}", link=f"/customers/{customer.id}")
    return scan
