from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.customer import Customer
from app.models.segment import Segment
from app.schemas.segment import SegmentCreate, SegmentFilters, SegmentUpdate


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


def resolve_members(db: Session, org_id: UUID, filters: SegmentFilters) -> list[Customer]:
    """Always run fresh against current data - a segment is a live
    definition, never a cached snapshot, so "customers who bought in the
    last 30 days" means today's answer every time it's opened."""
    q = db.query(Customer).options(joinedload(Customer.transactions)).filter(Customer.org_id == org_id)

    if filters.status:
        q = q.filter(Customer.status == filters.status)
    if filters.has_consent is True:
        q = q.filter(Customer.consent_date.isnot(None))
    elif filters.has_consent is False:
        q = q.filter(Customer.consent_date.is_(None))
    if filters.interest_contains:
        q = q.filter(func.lower(func.coalesce(Customer.interests, "")).like(f"%{filters.interest_contains.lower()}%"))
    if filters.search:
        like = f"%{filters.search.lower()}%"
        q = q.filter(
            or_(
                func.lower(Customer.name).like(like),
                func.lower(func.coalesce(Customer.phone, "")).like(like),
                func.lower(func.coalesce(Customer.email, "")).like(like),
            )
        )

    customers = q.all()

    if filters.min_transactions is not None:
        customers = [c for c in customers if len(c.transactions) >= filters.min_transactions]

    if filters.last_purchase_within_days is not None:
        cutoff = date.today() - timedelta(days=filters.last_purchase_within_days)
        customers = [c for c in customers if any(t.date >= cutoff for t in c.transactions)]

    if filters.last_purchase_over_days is not None:
        cutoff = date.today() - timedelta(days=filters.last_purchase_over_days)

        def is_stale(c: Customer) -> bool:
            if not c.transactions:
                return True  # never purchased counts as "overdue" for win-back targeting
            return max(t.date for t in c.transactions) < cutoff

        customers = [c for c in customers if is_stale(c)]

    return customers
