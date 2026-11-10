from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer
from app.schemas.summary import InterestCustomer, InterestRollup, MonthTotal, SummaryOut, TopCustomer


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _add_months(d: date, delta: int) -> date:
    month = d.month - 1 + delta
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


def _in_range(d: date, start_date: date | None, end_date: date | None) -> bool:
    if start_date and d < start_date:
        return False
    if end_date and d > end_date:
        return False
    return True


def _transaction_aggregates(
    customers: list[Customer], start_date: date | None, end_date: date | None
) -> tuple[dict[str, float], dict[tuple[str, str], float], dict[tuple[UUID, str], float]]:
    """Scans every transaction once, filtered by tx date when a range is
    given. Shared by the compact summary and the two "full view" drill-down
    endpoints so the scanning/bucketing logic only lives in one place.
    Transactions are scoped by their own date, independent of when the
    customer was created - a customer acquired last year who buys again this
    quarter should still count toward this quarter's sales."""
    totals: dict[str, float] = defaultdict(float)
    by_month: dict[tuple[str, str], float] = defaultdict(float)
    per_customer_currency: dict[tuple[UUID, str], float] = defaultdict(float)

    for c in customers:
        for tx in c.transactions:
            if not _in_range(tx.date, start_date, end_date):
                continue
            value = float(tx.amount or 0)
            if not value:
                continue
            currency = (tx.currency or "").upper()
            totals[currency] += value
            by_month[(_month_key(tx.date), currency)] += value
            per_customer_currency[(c.id, currency)] += value

    return dict(totals), dict(by_month), dict(per_customer_currency)


def _top_customers_from(
    customers: list[Customer], per_customer_currency: dict[tuple[UUID, str], float], limit: int
) -> list[TopCustomer]:
    by_currency: dict[str, list[tuple[Customer, float]]] = defaultdict(list)
    customer_by_id = {c.id: c for c in customers}
    for (cust_id, currency), total in per_customer_currency.items():
        by_currency[currency].append((customer_by_id[cust_id], total))

    top: list[TopCustomer] = []
    for currency, entries in by_currency.items():
        entries.sort(key=lambda x: x[1], reverse=True)
        for customer, total in entries[:limit]:
            top.append(TopCustomer(customer_id=str(customer.id), name=customer.name, currency=currency, total=total))
    return top


def get_summary(db: Session, org_id: UUID, start_date: date | None = None, end_date: date | None = None) -> SummaryOut:
    ranged = start_date is not None or end_date is not None
    customers = db.query(Customer).options(joinedload(Customer.transactions)).filter(Customer.org_id == org_id).all()

    # Customer-level facts (count, status, consent, interests) only carry
    # their own created_at date, so that's what a range filters them by.
    customer_scope = [c for c in customers if _in_range(c.created_at.date(), start_date, end_date)] if ranged else customers

    status_counts: dict[str, int] = defaultdict(int)
    without_consent = 0
    interest_map: dict[str, dict] = {}
    for c in customer_scope:
        status_counts[c.status.value] += 1
        if not c.consent_date:
            without_consent += 1
        for part in (c.interests or "").split(","):
            name = part.strip()
            if not name:
                continue
            entry = interest_map.setdefault(name.lower(), {"name": name, "customers": []})
            entry["customers"].append(InterestCustomer(id=str(c.id), name=c.name))

    all_time, by_month, per_customer_currency = _transaction_aggregates(customers, start_date, end_date)

    this_month: dict[str, float] = {}
    if not ranged:
        today = date.today()
        current_month = _month_key(today)
        this_month = {cur: amt for (mk, cur), amt in by_month.items() if mk == current_month}

    if ranged:
        touched_months = sorted({mk for (mk, _cur) in by_month.keys()})[-24:]
        months = [MonthTotal(month=mk, totals={cur: amt for (m2, cur), amt in by_month.items() if m2 == mk}) for mk in touched_months]
    else:
        today = date.today()
        months = []
        cursor = date(today.year, today.month, 1)
        for i in range(5, -1, -1):
            m = _add_months(cursor, -i)
            key = _month_key(m)
            totals = {cur: amt for (mk, cur), amt in by_month.items() if mk == key}
            months.append(MonthTotal(month=key, totals=totals))

    top_customers = _top_customers_from(customers, per_customer_currency, limit=5)

    interests = [
        InterestRollup(interest=v["name"], customers=v["customers"])
        for v in sorted(interest_map.values(), key=lambda v: len(v["customers"]), reverse=True)
    ]

    return SummaryOut(
        total_customers=len(customer_scope),
        status_counts=dict(status_counts),
        without_consent=without_consent,
        all_time_by_currency=all_time,
        this_month_by_currency=this_month,
        last_6_months=months,
        top_customers=top_customers,
        interests=interests,
        range_start=start_date,
        range_end=end_date,
    )


def get_full_top_customers(db: Session, org_id: UUID, start_date: date | None = None, end_date: date | None = None, limit: int = 50) -> list[TopCustomer]:
    customers = db.query(Customer).options(joinedload(Customer.transactions)).filter(Customer.org_id == org_id).all()
    _, _, per_customer_currency = _transaction_aggregates(customers, start_date, end_date)
    return _top_customers_from(customers, per_customer_currency, limit=limit)


def get_full_months(db: Session, org_id: UUID, start_date: date | None = None, end_date: date | None = None) -> list[MonthTotal]:
    customers = db.query(Customer).options(joinedload(Customer.transactions)).filter(Customer.org_id == org_id).all()
    _, by_month, _ = _transaction_aggregates(customers, start_date, end_date)
    touched_months = sorted({mk for (mk, _cur) in by_month.keys()})
    return [MonthTotal(month=mk, totals={cur: amt for (m2, cur), amt in by_month.items() if m2 == mk}) for mk in touched_months]
