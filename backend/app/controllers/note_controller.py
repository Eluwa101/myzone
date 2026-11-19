from uuid import UUID

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.controllers import notification_controller, webhook_controller
from app.core.paging import contains_any, like_pattern
from app.models.customer import Customer
from app.models.org_note import OrgNote
from app.schemas.note import NoteCreate, NoteUpdate


class NoteNotFoundError(Exception):
    pass


def _resolve_customers(db: Session, org_id: UUID, customer_ids: list[UUID]) -> list[Customer]:
    if not customer_ids:
        return []
    return db.query(Customer).filter(Customer.org_id == org_id, Customer.id.in_(customer_ids)).all()


def create_note(
    db: Session,
    org_id: UUID,
    data: NoteCreate,
    created_by_agent: bool = False,
    is_pending_review: bool = False,
) -> OrgNote:
    note = OrgNote(
        org_id=org_id,
        title=data.title,
        content=data.content,
        is_pending_review=is_pending_review,
        created_by_agent=created_by_agent,
    )
    note.customers = _resolve_customers(db, org_id, data.customer_ids)
    db.add(note)
    db.commit()
    db.refresh(note)
    webhook_controller.dispatch_event(db, org_id, "note.created", webhook_controller.note_payload(note))
    if is_pending_review:
        notification_controller.create_notification(db, org_id, "note.pending_review", f"Note needs review: {note.title}", link="/notes")
    return note


def query_notes(
    db: Session, org_id: UUID, customer_id: UUID | None = None, pending_only: bool = False, search: str | None = None
):
    q = db.query(OrgNote).options(joinedload(OrgNote.customers)).filter(OrgNote.org_id == org_id)
    if customer_id:
        q = q.filter(OrgNote.customers.any(Customer.id == customer_id))
    if pending_only:
        q = q.filter(OrgNote.is_pending_review.is_(True))
    pattern = like_pattern(search)
    if pattern:
        q = q.filter(
            or_(
                contains_any(pattern, OrgNote.title, OrgNote.content),
                OrgNote.customers.any(contains_any(pattern, Customer.name)),
            )
        )
    return q.order_by(OrgNote.created_at.desc(), OrgNote.id)


def list_notes(
    db: Session, org_id: UUID, customer_id: UUID | None = None, pending_only: bool = False, search: str | None = None
) -> list[OrgNote]:
    return query_notes(db, org_id, customer_id, pending_only, search).all()


def get_note(db: Session, org_id: UUID, note_id: UUID) -> OrgNote:
    return _get_note(db, org_id, note_id)


def count_pending(db: Session, org_id: UUID) -> int:
    return db.query(OrgNote).filter(OrgNote.org_id == org_id, OrgNote.is_pending_review.is_(True)).count()


def _get_note(db: Session, org_id: UUID, note_id: UUID) -> OrgNote:
    note = db.query(OrgNote).filter(OrgNote.org_id == org_id, OrgNote.id == note_id).first()
    if not note:
        raise NoteNotFoundError()
    return note


def update_note(db: Session, org_id: UUID, note_id: UUID, data: NoteUpdate) -> OrgNote:
    note = _get_note(db, org_id, note_id)
    updates = data.model_dump(exclude_unset=True, exclude={"customer_ids"})
    for field, value in updates.items():
        setattr(note, field, value)
    if data.customer_ids is not None:
        note.customers = _resolve_customers(db, org_id, data.customer_ids)
    db.commit()
    db.refresh(note)
    webhook_controller.dispatch_event(db, org_id, "note.updated", webhook_controller.note_payload(note))
    return note


def delete_note(db: Session, org_id: UUID, note_id: UUID) -> None:
    note = _get_note(db, org_id, note_id)
    payload = webhook_controller.note_payload(note)
    db.delete(note)
    db.commit()
    webhook_controller.dispatch_event(db, org_id, "note.deleted", payload)
