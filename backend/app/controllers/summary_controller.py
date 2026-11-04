from collections import defaultdict
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer
from app.schemas.summary import InterestRollup, MonthTotal, SummaryOut, TopCustomer


def _month_key(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _add_months(d: date, delta: int) -> date:
    month = d.month - 1 + delta
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, 1)


def get_summary(db: Session, org_id: UUID) -> SummaryOut:
    customers = db.query(Customer).options(joinedload(Customer.transactions)).filter(Customer.org_id == org_id).all()

    status_counts: dict[str, int] = defaultdict(int)
    without_consent = 0
    all_time: dict[str, float] = defaultdict(float)
    this_month: dict[str, float] = defaultdict(float)
    by_month: dict[tuple[str, str], float] = defaultdict(float)
    per_customer_currency: dict[tuple[UUID, str], float] = defaultdict(float)
    interest_map: dict[str, dict] = {}

    today = date.today()
    current_month = _month_key(today)

    for c in customers:
        status_counts[c.status.value] += 1
        if not c.consent_date:
            without_consent += 1

        for tx in c.transactions:
            value = float(tx.amount or 0) * float(tx.qty or 1)
            if not value:
                continue
            currency = (tx.currency or "").upper()
            all_time[currency] += value
            m = _month_key(tx.date)
            if m == current_month:
                this_month[currency] += value
            by_month[(m, currency)] += value
            per_customer_currency[(c.id, currency)] += value

        for part in (c.interests or "").split(","):
            name = part.strip()
            if not name:
                continue
            key = name.lower()
            entry = interest_map.setdefault(key, {"name": name, "customers": []})
            entry["customers"].append(c.name)

    months: list[MonthTotal] = []
    cursor = date(today.year, today.month, 1)
    for i in range(5, -1, -1):
        m = _add_months(cursor, -i)
        key = _month_key(m)
        totals = {cur: amt for (mk, cur), amt in by_month.items() if mk == key}
        months.append(MonthTotal(month=key, totals=totals))

    by_currency: dict[str, list[tuple[Customer, float]]] = defaultdict(list)
    customer_by_id = {c.id: c for c in customers}
    for (cust_id, currency), total in per_customer_currency.items():
        by_currency[currency].append((customer_by_id[cust_id], total))

    top_customers: list[TopCustomer] = []
    for currency, entries in by_currency.items():
        entries.sort(key=lambda x: x[1], reverse=True)
        for customer, total in entries[:5]:
            top_customers.append(TopCustomer(customer_id=str(customer.id), name=customer.name, currency=currency, total=total))

    interests = [
        InterestRollup(interest=v["name"], customers=v["customers"])
        for v in sorted(interest_map.values(), key=lambda v: len(v["customers"]), reverse=True)
    ]

    return SummaryOut(
        total_customers=len(customers),
        status_counts=dict(status_counts),
        without_consent=without_consent,
        all_time_by_currency=dict(all_time),
        this_month_by_currency=dict(this_month),
        last_6_months=months,
        top_customers=top_customers,
        interests=interests,
    )
