import csv
import io
import re
from uuid import UUID

from sqlalchemy import Text, func, or_
from sqlalchemy.orm import Session, joinedload

from app.controllers import notification_controller, webhook_controller
from app.models.customer import Customer, CustomerStatus
from app.models.organization import Organization
from app.models.transaction import Transaction
from app.schemas.customer import CustomerCreate, CustomerUpdate, ImportResult

# --- errors -----------------------------------------------------------------


class CustomerNotFoundError(Exception):
    pass


class DuplicateCustomerError(Exception):
    def __init__(self, existing: Customer):
        self.existing = existing


# --- dedup matching (ported from the prototype's pk()/nm()/same()) ----------


def _normalize_phone(phone: str | None) -> str:
    digits = re.sub(r"\D", "", phone or "")
    return digits[-9:] if len(digits) >= 7 else ""


def _normalize_name(name: str | None) -> str:
    return re.sub(r"\s+", " ", (name or "").lower()).strip()


def _is_duplicate(existing: Customer, candidate: dict) -> bool:
    pa, pb = _normalize_phone(existing.phone), _normalize_phone(candidate.get("phone"))
    ea = (existing.email or "").lower().strip()
    eb = (candidate.get("email") or "").lower().strip()
    if pa and pa == pb:
        return True
    if ea and ea == eb:
        return True
    na, nb = _normalize_name(existing.name), _normalize_name(candidate.get("name"))
    return bool(na) and na == nb and (not pa or not pb) and (not ea or not eb)


def find_match(db: Session, org_id: UUID, candidate: dict, exclude_id: UUID | None = None) -> Customer | None:
    q = db.query(Customer).filter(Customer.org_id == org_id)
    if exclude_id:
        q = q.filter(Customer.id != exclude_id)
    for existing in q.all():
        if _is_duplicate(existing, candidate):
            return existing
    return None


def find_duplicate_groups(db: Session, org_id: UUID) -> list[list[Customer]]:
    customers = db.query(Customer).options(joinedload(Customer.transactions)).filter(Customer.org_id == org_id).all()
    used: set[UUID] = set()
    groups: list[list[Customer]] = []
    for c in customers:
        if c.id in used:
            continue
        group = [c]
        used.add(c.id)
        changed = True
        while changed:
            changed = False
            for other in customers:
                if other.id in used:
                    continue
                cand = {"phone": other.phone, "email": other.email, "name": other.name}
                if any(_is_duplicate(g, cand) for g in group):
                    group.append(other)
                    used.add(other.id)
                    changed = True
        if len(group) > 1:
            group.sort(key=lambda x: x.created_at)
            groups.append(group)
    return groups


# --- derived fields (ported from clearBought()/autoStatus()) ----------------


def _clear_bought_interests(customer: Customer) -> None:
    if not customer.interests:
        return
    items = [
        li["item"].lower().strip()
        for t in customer.transactions
        for li in (t.items or [])
        if li.get("item") and len(li["item"].strip()) > 2
    ]
    kept = []
    for part in customer.interests.split(","):
        s = part.strip()
        if not s:
            continue
        low = s.lower()
        if any(it in low or low in it for it in items):
            continue
        kept.append(s)
    customer.interests = ", ".join(kept)


def split_name(name: str) -> tuple[str, str | None]:
    """Splits a full name into (first_name, last_name) the way the AI
    agent stores a name it's given in conversation: the first word is the
    first name, everything after is the last name, and a single word has
    no last name at all."""
    parts = name.strip().split(None, 1)
    if not parts:
        return "", None
    if len(parts) == 1:
        return parts[0], None
    return parts[0], parts[1]


def _tx_key(date, items: list[dict], amount: float) -> tuple:
    """A hashable fingerprint for a transaction, used to dedupe identical
    rows when merging customers or re-importing the same CSV twice."""
    item_key = tuple(sorted(((li.get("item") or "").lower(), float(li.get("qty") or 0), float(li.get("amount") or 0)) for li in items))
    return (date, item_key, round(float(amount), 2))


def _recompute_status(customer: Customer) -> None:
    if not customer.status_auto:
        return
    has_txs = len(customer.transactions) > 0
    has_interests = bool(customer.interests and customer.interests.strip())
    customer.status = CustomerStatus.customer if has_txs else (CustomerStatus.lead if has_interests else CustomerStatus.customer)


def recompute_derived_fields(customer: Customer) -> None:
    _clear_bought_interests(customer)
    _recompute_status(customer)


# --- CRUD ---------------------------------------------------------------


def get_customer(db: Session, org_id: UUID, customer_id: UUID) -> Customer:
    customer = (
        db.query(Customer)
        .options(joinedload(Customer.transactions), joinedload(Customer.orders))
        .filter(Customer.org_id == org_id, Customer.id == customer_id)
        .first()
    )
    if not customer:
        raise CustomerNotFoundError()
    return customer


def get_customer_by_display_id(db: Session, org_id: UUID, display_id: str) -> Customer:
    customer = (
        db.query(Customer)
        .options(joinedload(Customer.transactions), joinedload(Customer.orders))
        .filter(Customer.org_id == org_id, func.upper(Customer.display_id) == display_id.strip().upper())
        .first()
    )
    if not customer:
        raise CustomerNotFoundError()
    return customer


def list_customers(
    db: Session,
    org_id: UUID,
    search: str | None = None,
    status: CustomerStatus | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[Customer], int]:
    q = db.query(Customer).options(joinedload(Customer.transactions), joinedload(Customer.orders)).filter(Customer.org_id == org_id)
    if status:
        q = q.filter(Customer.status == status)
    if search:
        like = f"%{search.lower()}%"
        # Deep match: also searches inside each transaction's line items
        # (e.g. "Rice" finds every customer who bought rice) by casting the
        # JSON column to text - crude, but correct at this app's data scale,
        # and avoids a second paginated query to merge results from.
        tx_item_match = (
            db.query(Transaction.customer_id)
            .filter(func.lower(Transaction.items.cast(Text)).like(like))
            .subquery()
        )
        q = q.filter(
            or_(
                func.lower(Customer.name).like(like),
                func.lower(func.coalesce(Customer.phone, "")).like(like),
                func.lower(func.coalesce(Customer.email, "")).like(like),
                func.lower(func.coalesce(Customer.job, "")).like(like),
                func.lower(func.coalesce(Customer.pet, "")).like(like),
                func.lower(func.coalesce(Customer.interests, "")).like(like),
                func.lower(Customer.display_id).like(like),
                Customer.id.in_(db.query(tx_item_match.c.customer_id)),
            )
        )
    total = q.count()
    # id as a tie-breaker: without it two customers with the same name can
    # swap places between requests, and one shows on two pages while the
    # other shows on none
    page, page_size = max(1, page), min(max(1, page_size), 200)
    items = q.order_by(func.lower(Customer.name), Customer.id).offset((page - 1) * page_size).limit(page_size).all()
    return items, total


def _apply_status(customer: Customer, status: CustomerStatus | None) -> None:
    if status is not None:
        customer.status = status
        customer.status_auto = False
    else:
        customer.status_auto = True


def _next_display_id(db: Session, org_id: UUID) -> str:
    """CR001, CR002, ... scoped to this org. Locks the org row for the rest
    of this transaction so two concurrent creates can't be handed the same
    number (with_for_update is a no-op on SQLite, which is fine - the test
    suite never creates customers concurrently)."""
    org = db.query(Organization).filter(Organization.id == org_id).with_for_update().one()
    org.customer_seq += 1
    return f"CR{org.customer_seq:03d}"


def create_customer(db: Session, org_id: UUID, data: CustomerCreate, force: bool = False) -> Customer:
    if not force:
        match = find_match(db, org_id, data.model_dump())
        if match:
            raise DuplicateCustomerError(match)

    customer = Customer(
        org_id=org_id,
        display_id=_next_display_id(db, org_id),
        name=data.name,
        first_name=data.first_name,
        last_name=data.last_name,
        phone=data.phone,
        email=data.email,
        job=data.job,
        nationality=data.nationality,
        pet=data.pet,
        birthday=data.birthday,
        address=data.address,
        notes=data.notes,
        interests=data.interests,
        consent_date=data.consent_date,
        extra=data.extra or {},
    )
    _apply_status(customer, data.status)
    recompute_derived_fields(customer)
    db.add(customer)
    db.commit()
    db.refresh(customer)
    webhook_controller.dispatch_event(db, org_id, "customer.created", webhook_controller.customer_payload(customer))
    return customer


def update_customer(db: Session, org_id: UUID, customer_id: UUID, data: CustomerUpdate) -> Customer:
    customer = get_customer(db, org_id, customer_id)
    updates = data.model_dump(exclude_unset=True)
    status = updates.pop("status", "__unset__")
    for field, value in updates.items():
        setattr(customer, field, value)
    if "first_name" in updates or "last_name" in updates:
        combined = f"{customer.first_name or ''} {customer.last_name or ''}".strip()
        if combined:
            customer.name = combined
    if status != "__unset__":
        _apply_status(customer, status)
    recompute_derived_fields(customer)
    db.commit()
    db.refresh(customer)
    webhook_controller.dispatch_event(db, org_id, "customer.updated", webhook_controller.customer_payload(customer))
    return customer


def delete_customer(db: Session, org_id: UUID, customer_id: UUID) -> None:
    customer = get_customer(db, org_id, customer_id)
    payload = webhook_controller.customer_payload(customer)
    db.delete(customer)
    db.commit()
    webhook_controller.dispatch_event(db, org_id, "customer.deleted", payload)


def merge_customers(db: Session, org_id: UUID, keep_id: UUID, merge_id: UUID) -> Customer:
    keep = get_customer(db, org_id, keep_id)
    merge = get_customer(db, org_id, merge_id)

    for field in ["phone", "email", "job", "nationality", "pet", "birthday", "address", "consent_date"]:
        if not getattr(keep, field) and getattr(merge, field):
            setattr(keep, field, getattr(merge, field))

    seen, parts = set(), []
    for part in (keep.interests or "").split(",") + (merge.interests or "").split(","):
        s = part.strip()
        if s and s.lower() not in seen:
            seen.add(s.lower())
            parts.append(s)
    keep.interests = ", ".join(parts)

    n1, n2 = (keep.notes or "").strip(), (merge.notes or "").strip()
    keep.notes = (n1 + " | " + n2) if (n1 and n2 and n1 != n2) else (n1 or n2)

    merged_extra = dict(merge.extra or {})
    merged_extra.update(keep.extra or {})
    keep.extra = merged_extra

    existing_keys = {_tx_key(t.date, t.items or [], t.amount) for t in keep.transactions}
    for tx in list(merge.transactions):
        key = _tx_key(tx.date, tx.items or [], tx.amount)
        if key in existing_keys:
            db.delete(tx)
        else:
            tx.customer_id = keep.id
            existing_keys.add(key)
    db.flush()

    recompute_derived_fields(keep)
    db.delete(merge)
    db.commit()
    db.refresh(keep)
    return keep


# --- CSV import/export (ported from AL/normH + the import/export handlers) --

_ALIASES: dict[str, list[str]] = {
    "name": ["name", "full name", "fullname", "customer", "customer name", "client", "client name", "contact", "contact name"],
    "phone": ["phone", "phone number", "mobile", "mobile number", "tel", "telephone", "whatsapp", "whatsapp number", "cell", "contact number"],
    "email": ["email", "e-mail", "email address", "mail"],
    "job": ["job", "job title", "occupation", "profession", "work", "position"],
    "nationality": ["nat", "nationality", "country", "citizenship"],
    "pet": ["pet", "pets"],
    "birthday": ["bday", "birthday", "birth date", "date of birth", "dob"],
    "address": ["addr", "address", "city", "location"],
    "notes": ["notes", "note", "comments", "comment", "remarks"],
    "interests": ["interests", "interest", "interested in", "products of interest"],
    "status": ["status", "type", "customer type", "stage"],
    "consent_date": ["consent", "consent date", "consented", "consent given"],
}
_TX_ALIASES: dict[str, list[str]] = {
    "date": ["date", "txn_date", "transaction date", "purchase date"],
    "item": ["item", "txn_item", "product", "products", "items", "transaction item", "description"],
    "qty": ["qty", "txn_qty", "quantity", "units"],
    "amount": ["amount", "txn_amount", "price", "cost"],
    "currency": ["currency", "txn_currency", "curr", "ccy"],
}
CUSTOMER_FIELDS = list(_ALIASES.keys())
TX_FIELDS = list(_TX_ALIASES.keys())


def _normalize_header(h: str) -> str:
    h = h.strip()
    low = h.lower()
    if low.startswith("extra:"):
        return "extra:" + h[6:].strip()
    for key, names in {**_ALIASES, **_TX_ALIASES}.items():
        if low in names:
            return key
    return low


def _sniff_delimiter(sample: str) -> str:
    first_line = sample.split("\n", 1)[0]
    best, best_count = ",", first_line.count(",")
    for d in [";", "\t"]:
        c = first_line.count(d)
        if c > best_count:
            best, best_count = d, c
    return best


def import_csv(db: Session, org_id: UUID, csv_text: str) -> ImportResult:
    csv_text = csv_text.lstrip("﻿")
    if not csv_text.strip():
        return ImportResult(added=0, merged=0, skipped=0, failed=0, errors=["Empty CSV."])

    delimiter = _sniff_delimiter(csv_text)
    reader = csv.reader(io.StringIO(csv_text), delimiter=delimiter)
    rows = [r for r in reader if any(cell.strip() for cell in r)]
    if len(rows) < 2:
        return ImportResult(added=0, merged=0, skipped=0, failed=0, errors=["Needs a header row plus at least one data row."])

    headers = [_normalize_header(h) for h in rows[0]]
    if "name" not in headers:
        return ImportResult(added=0, merged=0, skipped=0, failed=0, errors=[f"No name column found. Columns seen: {', '.join(rows[0])}."])

    grouped: dict[str, dict] = {}
    skipped = 0
    for row in rows[1:]:
        record = {h: (row[i].strip() if i < len(row) else "") for i, h in enumerate(headers)}
        name = record.get("name", "").strip()
        if not name:
            skipped += 1
            continue
        key = f"{name.lower()}|{record.get('phone', '')}"
        group = grouped.setdefault(key, {"fields": {}, "extra": {}, "txs": []})
        for field in CUSTOMER_FIELDS:
            value = record.get(field, "")
            if value and not group["fields"].get(field):
                group["fields"][field] = value
        for header, value in record.items():
            if header in CUSTOMER_FIELDS or header in TX_FIELDS or not value:
                continue
            label = header[6:].strip() if header.startswith("extra:") else header.capitalize()
            label = re.sub(r"[./\[\]*~`]", " ", label).strip()
            if label and not group["extra"].get(label):
                group["extra"][label] = value
        if record.get("item") or record.get("amount"):
            group["txs"].append(
                {
                    "date": record.get("date") or "",
                    "item": record.get("item") or "",
                    "qty": record.get("qty") or "1",
                    "amount": record.get("amount") or "0",
                    "currency": (record.get("currency") or "").upper(),
                }
            )

    added = merged = failed = 0
    errors: list[str] = []
    for group in grouped.values():
        try:
            fields = group["fields"]
            if not fields.get("name"):
                skipped += 1
                continue
            data = CustomerCreate(
                name=fields["name"],
                phone=fields.get("phone"),
                email=fields.get("email"),
                job=fields.get("job"),
                nationality=fields.get("nationality"),
                pet=fields.get("pet"),
                address=fields.get("address"),
                notes=fields.get("notes"),
                interests=fields.get("interests"),
                extra=group["extra"],
            )
            match = find_match(db, org_id, data.model_dump())
            if match:
                for f in CUSTOMER_FIELDS:
                    if f in ("status",):
                        continue
                    if not getattr(match, f, None) and fields.get(f):
                        setattr(match, f, fields.get(f))
                match.extra = {**group["extra"], **(match.extra or {})}
                existing_keys = {_tx_key(t.date, t.items or [], t.amount) for t in match.transactions}
                for tx in group["txs"]:
                    import datetime as _dt

                    tx_date = _parse_date(tx["date"]) or _dt.date.today()
                    tx_amount = float(tx["amount"] or 0)
                    tx_items = [{"item": tx["item"], "qty": float(tx["qty"] or 1), "amount": tx_amount}]
                    tx_key = _tx_key(tx_date, tx_items, tx_amount)
                    if tx_key in existing_keys:
                        continue
                    match.transactions.append(Transaction(date=tx_date, items=tx_items, amount=tx_amount, currency=tx["currency"]))
                    existing_keys.add(tx_key)
                recompute_derived_fields(match)
                db.commit()
                merged += 1
            else:
                customer = create_customer(db, org_id, data, force=True)
                for tx in group["txs"]:
                    tx_date = _parse_date(tx["date"]) or customer.created_at.date()
                    tx_amount = float(tx["amount"] or 0)
                    tx_items = [{"item": tx["item"], "qty": float(tx["qty"] or 1), "amount": tx_amount}]
                    customer.transactions.append(Transaction(date=tx_date, items=tx_items, amount=tx_amount, currency=tx["currency"]))
                recompute_derived_fields(customer)
                db.commit()
                added += 1
        except Exception as e:  # noqa: BLE001 - surfaced to the caller, not swallowed silently
            failed += 1
            errors.append(str(e))
            db.rollback()

    notification_type = "import.failed" if failed and not (added or merged) else "import.completed"
    notification_controller.create_notification(
        db,
        org_id,
        notification_type,
        f"CSV import finished: {added} added, {merged} updated" + (f", {failed} failed" if failed else ""),
        body=("; ".join(errors[:5]) + ("…" if len(errors) > 5 else "")) if errors else None,
        link="/data",
    )
    return ImportResult(added=added, merged=merged, skipped=skipped, failed=failed, errors=errors)


def _parse_date(value: str):
    import datetime as _dt

    if not value:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return _dt.datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def export_csv(db: Session, org_id: UUID) -> str:
    customers = db.query(Customer).options(joinedload(Customer.transactions)).filter(Customer.org_id == org_id).order_by(Customer.name).all()
    extra_keys: list[str] = []
    for c in customers:
        for k in (c.extra or {}):
            if k not in extra_keys:
                extra_keys.append(k)

    header = (
        ["name", "phone", "email", "job", "nationality", "pet", "birthday", "address", "notes", "interests", "status", "consent_date"]
        + [f"extra:{k}" for k in extra_keys]
        + ["txn_date", "txn_item", "txn_qty", "txn_amount", "txn_currency"]
    )

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(header)
    for c in customers:
        base = [
            c.name, c.phone or "", c.email or "", c.job or "", c.nationality or "", c.pet or "",
            c.birthday.isoformat() if c.birthday else "", c.address or "", c.notes or "", c.interests or "",
            c.status.value, c.consent_date.isoformat() if c.consent_date else "",
        ]
        extra_vals = [(c.extra or {}).get(k, "") for k in extra_keys]
        # One CSV row per transaction line item (a multi-item transaction
        # re-imports as separate transactions - an accepted round-trip
        # limitation of the flat CSV format).
        rows = [(t, li) for t in c.transactions for li in (t.items or [])]
        if not rows:
            writer.writerow(base + extra_vals + ["", "", "", "", ""])
        else:
            for t, li in rows:
                writer.writerow(base + extra_vals + [t.date.isoformat(), li.get("item", ""), li.get("qty", ""), li.get("amount", ""), t.currency])
    return buf.getvalue()
