"""Resolves {{category.field}} placeholders in a message template against
one customer, at send time - never client-side, so what's actually in the
customer's inbox always reflects live data, not whatever was true when the
template was drafted.

Alongside the plain data fields (a customer's name, a business's phone
number, ...), this also computes arithmetic/date tags - lifetime spend,
days since last purchase, age, days until a delivery is due, and so on -
from the same underlying data, so a template can say "it's been {{stats.
days_since_last_purchase}} days" without the business having to compute
that themselves. These are plain Python functions, not a user-authorable
formula language: letting template text itself define arbitrary
expressions would be a code-execution surface, so for now new computed
tags are added here deliberately rather than self-served.

Money fields that sum across a customer's transactions/orders (lifetime
spend, unpaid total, ...) add up `amount` regardless of currency - fine for
the common case of one business trading in one currency, but a customer
who has been invoiced in more than one currency will get a number that
mixes them. Same simplification segment_controller's total_spent field
already makes.

The catalog (`available_merge_tags`) is the single source of truth the
frontend's tag picker renders from, so the picker can never drift out of
sync with what the resolver actually understands."""
import re
from dataclasses import dataclass
from datetime import date
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.controllers.segment_fields import list_custom_field_keys
from app.models.customer import Customer
from app.models.order import Order
from app.models.organization import Organization
from app.models.org_settings import OrgSettings
from app.models.transaction import Transaction

MISSING = "—"

TAG_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_]+)\.([a-zA-Z_]+)\s*\}\}")


@dataclass
class MergeTagContext:
    customer: Customer
    org: Organization
    org_settings: OrgSettings | None


def _latest(items: list, date_attr: str):
    dated = [i for i in items if getattr(i, date_attr, None)]
    return max(dated, key=lambda i: getattr(i, date_attr)) if dated else None


def _order_items_text(order: Order | None) -> str | None:
    if not order or not order.items:
        return None
    return ", ".join(f"{i['name']} x{i['qty']}" if i.get("qty", 1) != 1 else i["name"] for i in order.items)


def _tx_items_text(tx: Transaction | None) -> str | None:
    if not tx or not tx.items:
        return None
    return ", ".join(f"{i['item']} x{i['qty']}" if i.get("qty", 1) != 1 else i["item"] for i in tx.items)


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _age_years(c: Customer) -> int | None:
    if not c.birthday:
        return None
    today = date.today()
    b = c.birthday
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def _days_until_birthday(c: Customer) -> int | None:
    if not c.birthday:
        return None
    today = date.today()
    b = c.birthday
    for year in (today.year, today.year + 1):
        try:
            occurrence = b.replace(year=year)
        except ValueError:
            occurrence = date(year, 2, 28)  # the birthday is Feb 29 and `year` isn't a leap year
        if occurrence >= today:
            return (occurrence - today).days
    return None  # unreachable - the loop always finds this year's or next year's occurrence


def _days_as_customer(c: Customer) -> int:
    return (date.today() - c.created_at.date()).days


def _lifetime_spend(c: Customer) -> float:
    return sum(float(t.amount or 0) for t in c.transactions)


def _average_transaction(c: Customer) -> float | None:
    if not c.transactions:
        return None
    return _lifetime_spend(c) / len(c.transactions)


def _purchase_dates(c: Customer) -> list[date]:
    return [t.date for t in c.transactions] + [o.order_date for o in c.orders]


def _days_since_last_purchase(c: Customer) -> int | None:
    dates = _purchase_dates(c)
    return (date.today() - max(dates)).days if dates else None


def _first_purchase_date(c: Customer) -> str | None:
    dates = _purchase_dates(c)
    return min(dates).isoformat() if dates else None


def _unpaid_order_total(c: Customer) -> float:
    return sum(float(o.amount or 0) for o in c.orders if not o.paid and o.amount is not None)


def _days_since_ordered(o: Order | None) -> int | None:
    return (date.today() - o.order_date).days if o else None


def _days_until_delivery(o: Order | None) -> int | None:
    return (o.delivery_date - date.today()).days if o and o.delivery_date else None


def _order_overdue(o: Order | None) -> str | None:
    if not o or not o.delivery_date:
        return None
    return "Yes" if (not o.delivered and date.today() > o.delivery_date) else "No"


def _days_since_transaction(t: Transaction | None) -> int | None:
    return (date.today() - t.date).days if t else None


_CUSTOMER_FIELDS: dict[str, tuple[str, Callable[[Customer], object]]] = {
    "name": ("Full name", lambda c: c.name),
    "first_name": ("First name", lambda c: c.first_name),
    "last_name": ("Last name", lambda c: c.last_name),
    "phone": ("Phone", lambda c: c.phone),
    "email": ("Email", lambda c: c.email),
    "job": ("Job", lambda c: c.job),
    "pet": ("Pet", lambda c: c.pet),
    "address": ("Address", lambda c: c.address),
    "birthday": ("Birthday", lambda c: c.birthday.isoformat() if c.birthday else None),
    "age": ("Age (years)", _age_years),
    "days_until_birthday": ("Days until next birthday", _days_until_birthday),
    "days_as_customer": ("Days as a customer", _days_as_customer),
    "interests": ("Interested in", lambda c: c.interests),
    "display_id": ("Customer ID", lambda c: c.display_id),
    "status": ("Status", lambda c: c.status.value if c.status else None),
}

_BUSINESS_FIELDS: dict[str, tuple[str, Callable[["MergeTagContext"], object]]] = {
    "name": ("Business name", lambda ctx: (ctx.org_settings.biz_name if ctx.org_settings else None) or ctx.org.name),
    "industry": ("Industry", lambda ctx: ctx.org_settings.industry if ctx.org_settings else None),
    "manager_name": ("Manager name", lambda ctx: ctx.org_settings.manager_name if ctx.org_settings else None),
    "phone": ("Business phone", lambda ctx: ctx.org_settings.phone if ctx.org_settings else None),
    "address": ("Business address", lambda ctx: ctx.org_settings.address if ctx.org_settings else None),
    "whatsapp_number": ("WhatsApp number", lambda ctx: ctx.org_settings.whatsapp_number if ctx.org_settings else None),
}

_LATEST_ORDER_FIELDS: dict[str, tuple[str, Callable[[Order | None], object]]] = {
    "date": ("Date", lambda o: o.order_date.isoformat() if o else None),
    "items": ("Items", lambda o: _order_items_text(o)),
    "amount": ("Amount", lambda o: o.amount if o else None),
    "currency": ("Currency", lambda o: o.currency if o else None),
    "delivered": ("Delivered?", lambda o: ("Yes" if o.delivered else "No") if o else None),
    "days_since_ordered": ("Days since ordered", _days_since_ordered),
    "days_until_delivery": ("Days until delivery due", _days_until_delivery),
    "overdue": ("Delivery overdue?", _order_overdue),
}

_LATEST_TRANSACTION_FIELDS: dict[str, tuple[str, Callable[[Transaction | None], object]]] = {
    "date": ("Date", lambda t: t.date.isoformat() if t else None),
    "items": ("Items", lambda t: _tx_items_text(t)),
    "amount": ("Amount", lambda t: t.amount if t else None),
    "currency": ("Currency", lambda t: t.currency if t else None),
    "days_since": ("Days since", _days_since_transaction),
}

_STATS_FIELDS: dict[str, tuple[str, Callable[[Customer], object]]] = {
    "lifetime_spend": ("Lifetime spend", lambda c: _money(_lifetime_spend(c))),
    "transaction_count": ("Number of transactions", lambda c: len(c.transactions)),
    "order_count": ("Number of orders", lambda c: len(c.orders)),
    "average_transaction": ("Average transaction", lambda c: (_money(_average_transaction(c)) if _average_transaction(c) is not None else None)),
    "days_since_last_purchase": ("Days since last purchase", _days_since_last_purchase),
    "first_purchase_date": ("First purchase date", _first_purchase_date),
    "pending_order_count": ("Orders awaiting delivery", lambda c: sum(1 for o in c.orders if not o.delivered)),
    "unpaid_order_total": ("Unpaid orders total", lambda c: _money(_unpaid_order_total(c))),
}

_SYSTEM_FIELDS: dict[str, tuple[str, Callable[[], object]]] = {
    "today": ("Today's date", lambda: date.today().isoformat()),
    "year": ("Current year", lambda: date.today().year),
}

_CATEGORIES = [
    ("customer", "Customer", _CUSTOMER_FIELDS),
    ("business", "Business", _BUSINESS_FIELDS),
    ("latest_order", "Latest order", _LATEST_ORDER_FIELDS),
    ("latest_transaction", "Latest transaction", _LATEST_TRANSACTION_FIELDS),
    ("stats", "Purchase stats", _STATS_FIELDS),
    ("system", "Date", _SYSTEM_FIELDS),
]


def _slugify(key: str) -> str:
    """Custom "extra" fields are free text (spaces, punctuation, any case),
    but a merge tag's key has to be a plain identifier - this turns one into
    the other, consistently, so the same slug is produced both when the
    catalog is built and when a tag is resolved."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", key.strip()).strip("_").lower()
    return slug or "field"


def available_merge_tags(db: Session, org_id: UUID) -> list[dict]:
    """The full catalog for this org right now - the fixed categories above,
    plus one "extra.<field>" tag per custom field any of this org's
    customers currently has. Nothing is hardcoded for custom fields: a
    field created tomorrow (via CSV import, the agent, or a customer's Info
    tab) just appears here the next time this is called, with no code
    change needed."""
    tags = [
        {"category": category, "category_label": category_label, "key": key, "label": label, "tag": f"{{{{{category}.{key}}}}}"}
        for category, category_label, fields in _CATEGORIES
        for key, (label, _getter) in fields.items()
    ]

    seen_slugs: set[str] = set()
    for extra_key in list_custom_field_keys(db, org_id):
        slug = base_slug = _slugify(extra_key)
        i = 2
        while slug in seen_slugs:
            slug, i = f"{base_slug}_{i}", i + 1
        seen_slugs.add(slug)
        tags.append({"category": "extra", "category_label": "Custom fields", "key": slug, "label": extra_key, "tag": f"{{{{extra.{slug}}}}}"})

    return tags


def resolve_merge_tags(text: str, ctx: MergeTagContext) -> str:
    if not text or "{{" not in text:
        return text

    latest_order = _latest(ctx.customer.orders, "order_date")
    latest_tx = _latest(ctx.customer.transactions, "date")

    def replace(match: re.Match) -> str:
        category, key = match.group(1), match.group(2)
        if category == "customer" and key in _CUSTOMER_FIELDS:
            value = _CUSTOMER_FIELDS[key][1](ctx.customer)
        elif category == "business" and key in _BUSINESS_FIELDS:
            value = _BUSINESS_FIELDS[key][1](ctx)
        elif category == "latest_order" and key in _LATEST_ORDER_FIELDS:
            value = _LATEST_ORDER_FIELDS[key][1](latest_order)
        elif category == "latest_transaction" and key in _LATEST_TRANSACTION_FIELDS:
            value = _LATEST_TRANSACTION_FIELDS[key][1](latest_tx)
        elif category == "stats" and key in _STATS_FIELDS:
            value = _STATS_FIELDS[key][1](ctx.customer)
        elif category == "system" and key in _SYSTEM_FIELDS:
            value = _SYSTEM_FIELDS[key][1]()
        elif category == "extra":
            value = next((v for k, v in (ctx.customer.extra or {}).items() if _slugify(k) == key), None)
        else:
            return match.group(0)  # unknown tag - leave it as-is rather than guess
        return str(value) if value not in (None, "") else MISSING

    return TAG_PATTERN.sub(replace, text)
