"""The registry of fields a segment condition can target, shared by the
condition evaluator (segment_controller), the API that tells the frontend
what's available (routes/segments.py GET /fields), and the LLM prompt that
turns a description into a filter tree (agent/segment_suggest.py) - one
source of truth so all three always agree on what's queryable."""
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.customer import Customer
from app.schemas.segment import Operator

FieldType = Literal["text", "enum", "date", "number", "boolean"]


@dataclass(frozen=True)
class FieldDef:
    key: str
    label: str
    type: FieldType
    choices: list[str] | None = None


FIELD_REGISTRY: dict[str, FieldDef] = {
    f.key: f
    for f in [
        FieldDef("first_name", "First name", "text"),
        FieldDef("last_name", "Last name", "text"),
        FieldDef("phone", "Phone", "text"),
        FieldDef("email", "Email", "text"),
        FieldDef("job", "Job / occupation", "text"),
        FieldDef("nationality", "Nationality", "text"),
        FieldDef("pet", "Pet(s)", "text"),
        FieldDef("address", "Address / city", "text"),
        FieldDef("notes", "Notes", "text"),
        FieldDef("interests", "Interested in", "text"),
        FieldDef("status", "Status", "enum", choices=["lead", "customer", "inactive"]),
        FieldDef("birthday", "Birthday", "date"),
        FieldDef("consent_date", "Consent date", "date"),
        FieldDef("created_at", "Customer since", "date"),
        FieldDef("transaction_count", "Number of transactions", "number"),
        FieldDef("total_spent", "Total spent", "number"),
        FieldDef("last_purchase_date", "Last purchase date", "date"),
        FieldDef("first_purchase_date", "First purchase date", "date"),
        FieldDef("order_count", "Number of orders", "number"),
        FieldDef("has_unpaid_order", "Has an unpaid order", "boolean"),
        FieldDef("has_undelivered_order", "Has an undelivered order", "boolean"),
        FieldDef("last_order_date", "Last order date", "date"),
    ]
}

OPERATORS_BY_TYPE: dict[FieldType, list[Operator]] = {
    "text": ["equals", "not_equals", "contains", "not_contains", "in_list", "not_in_list", "is_set", "is_not_set"],
    "enum": ["equals", "not_equals", "in_list", "not_in_list"],
    "date": ["equals", "not_equals", "greater_than", "less_than", "between", "is_set", "is_not_set", "within_last_days", "over_days_ago"],
    "number": ["equals", "not_equals", "greater_than", "less_than", "between", "is_set", "is_not_set"],
    "boolean": ["equals"],
}


def field_type(field_key: str) -> FieldType:
    if field_key.startswith("extra."):
        return "text"
    known = FIELD_REGISTRY.get(field_key)
    return known.type if known else "text"


def list_custom_field_keys(db: Session, org_id: UUID) -> list[str]:
    """Every distinct key used in any customer's `extra` JSON for this org -
    these are offered as "extra.<key>" fields, same keys CSV export already
    surfaces as columns."""
    keys: list[str] = []
    for (extra,) in db.query(Customer.extra).filter(Customer.org_id == org_id).all():
        for k in extra or {}:
            if k not in keys:
                keys.append(k)
    return keys
