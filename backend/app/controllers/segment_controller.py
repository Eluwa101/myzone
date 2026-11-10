import datetime
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.controllers.segment_fields import field_type
from app.models.customer import Customer
from app.models.segment import Segment
from app.schemas.segment import SegmentCondition, SegmentCreate, SegmentFilters, SegmentGroup, SegmentUpdate


class SegmentNotFoundError(Exception):
    pass


def create_segment(db: Session, org_id: UUID, data: SegmentCreate) -> Segment:
    segment = Segment(org_id=org_id, name=data.name, filters=data.filters.model_dump(mode="json"))
    db.add(segment)
    db.commit()
    db.refresh(segment)
    return segment


def list_segments(db: Session, org_id: UUID) -> list[Segment]:
    return db.query(Segment).filter(Segment.org_id == org_id).order_by(Segment.created_at.desc()).all()


def get_segment(db: Session, org_id: UUID, segment_id: UUID) -> Segment:
    segment = db.query(Segment).filter(Segment.org_id == org_id, Segment.id == segment_id).first()
    if not segment:
        raise SegmentNotFoundError()
    return segment


def update_segment(db: Session, org_id: UUID, segment_id: UUID, data: SegmentUpdate) -> Segment:
    segment = get_segment(db, org_id, segment_id)
    if data.name is not None:
        segment.name = data.name
    if data.filters is not None:
        segment.filters = data.filters.model_dump(mode="json")
    db.commit()
    db.refresh(segment)
    return segment


def delete_segment(db: Session, org_id: UUID, segment_id: UUID) -> None:
    segment = get_segment(db, org_id, segment_id)
    db.delete(segment)
    db.commit()


# --- condition evaluation ---------------------------------------------------
#
# Conditions are evaluated in Python against each of the org's customers
# (eager-loaded with transactions/orders) rather than compiled into SQL.
# That keeps arbitrary AND/OR/NOR nesting and derived fields (total spent,
# last purchase date, "has an unpaid order", ...) simple and safe to add -
# no dynamic SQL to build or guard against - at a DB-efficiency cost that's
# a non-issue at small-business scale (hundreds, not millions, of rows).


def _field_value(customer: Customer, field: str):
    if field.startswith("extra."):
        return (customer.extra or {}).get(field[len("extra.") :])
    if field == "transaction_count":
        return len(customer.transactions)
    if field == "total_spent":
        return sum(float(t.amount or 0) for t in customer.transactions)
    if field == "last_purchase_date":
        dates = [t.date for t in customer.transactions]
        return max(dates) if dates else None
    if field == "first_purchase_date":
        dates = [t.date for t in customer.transactions]
        return min(dates) if dates else None
    if field == "order_count":
        return len(customer.orders)
    if field == "has_unpaid_order":
        return any(not o.paid for o in customer.orders)
    if field == "has_undelivered_order":
        return any(not o.delivered for o in customer.orders)
    if field == "last_order_date":
        dates = [o.order_date for o in customer.orders]
        return max(dates) if dates else None
    value = getattr(customer, field, None)
    return value.value if hasattr(value, "value") else value  # CustomerStatus enum -> its string


def _norm(value) -> str:
    return str(value).strip().lower()


def _as_number(value) -> float:
    return float(value)


def _as_date(value) -> datetime.date:
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    return datetime.date.fromisoformat(str(value))


def _evaluate_condition(cond: SegmentCondition, customer: Customer) -> bool:
    raw = _field_value(customer, cond.field)
    op = cond.operator

    if op == "is_set":
        return raw is not None and raw != ""
    if op == "is_not_set":
        return raw is None or raw == ""
    if raw is None and op == "over_days_ago" and cond.field in ("last_purchase_date", "last_order_date"):
        return True  # never purchased/ordered counts as "overdue" for win-back targeting
    if raw is None or raw == "":
        return False  # every other operator needs a value to compare against

    ftype = field_type(cond.field)

    if op == "equals":
        if ftype == "boolean":
            return bool(raw) == bool(cond.value)
        return _norm(raw) == _norm(cond.value)
    if op == "not_equals":
        if ftype == "boolean":
            return bool(raw) != bool(cond.value)
        return _norm(raw) != _norm(cond.value)
    if op == "contains":
        return _norm(cond.value) in _norm(raw)
    if op == "not_contains":
        return _norm(cond.value) not in _norm(raw)
    if op == "in_list":
        return _norm(raw) in [_norm(v) for v in (cond.values or [])]
    if op == "not_in_list":
        return _norm(raw) not in [_norm(v) for v in (cond.values or [])]

    if ftype == "date":
        today = datetime.date.today()
        if op == "greater_than":
            return _as_date(raw) > _as_date(cond.value)
        if op == "less_than":
            return _as_date(raw) < _as_date(cond.value)
        if op == "between":
            return _as_date(cond.value) <= _as_date(raw) <= _as_date(cond.value2)
        if op == "within_last_days":
            return _as_date(raw) >= today - datetime.timedelta(days=int(cond.value))
        if op == "over_days_ago":
            return _as_date(raw) < today - datetime.timedelta(days=int(cond.value))
    else:
        if op == "greater_than":
            return _as_number(raw) > _as_number(cond.value)
        if op == "less_than":
            return _as_number(raw) < _as_number(cond.value)
        if op == "between":
            return _as_number(cond.value) <= _as_number(raw) <= _as_number(cond.value2)

    return False


def _evaluate(node: SegmentCondition | SegmentGroup, customer: Customer) -> bool:
    if isinstance(node, SegmentCondition):
        return _evaluate_condition(node, customer)
    if not node.conditions:
        return True  # an empty group matches everyone
    results = [_evaluate(child, customer) for child in node.conditions]
    if node.combinator == "and":
        return all(results)
    if node.combinator == "or":
        return any(results)
    return not any(results)  # nor


def resolve_members(db: Session, org_id: UUID, filters: SegmentFilters) -> list[Customer]:
    """Always run fresh against current data - a segment is a live
    definition, never a cached snapshot, so "customers who bought in the
    last 30 days" means today's answer every time it's opened."""
    customers = (
        db.query(Customer)
        .options(joinedload(Customer.transactions), joinedload(Customer.orders))
        .filter(Customer.org_id == org_id)
        .all()
    )
    return [c for c in customers if _evaluate(filters, c)]
