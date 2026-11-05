from datetime import date

from pydantic import BaseModel


class MonthTotal(BaseModel):
    month: str
    totals: dict[str, float]


class TopCustomer(BaseModel):
    customer_id: str
    name: str
    currency: str
    total: float


class InterestCustomer(BaseModel):
    id: str
    name: str


class InterestRollup(BaseModel):
    interest: str
    customers: list[InterestCustomer]


class SummaryOut(BaseModel):
    total_customers: int
    status_counts: dict[str, int]
    without_consent: int
    all_time_by_currency: dict[str, float]
    this_month_by_currency: dict[str, float]
    last_6_months: list[MonthTotal]
    top_customers: list[TopCustomer]
    interests: list[InterestRollup]
    range_start: date | None = None
    range_end: date | None = None
