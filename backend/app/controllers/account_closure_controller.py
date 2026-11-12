"""Closing a business's account, as promised in the Privacy Policy (section
9) and Terms (section 9):

1. An owner asks to close it. The account becomes read-only for
   CLOSURE_GRACE_DAYS, so they can still export everything, and any owner
   can cancel in that time.
2. When the time is up, every row belonging to the business is
   permanently deleted - customers, sales, orders, notes, templates,
   messages, segments, forms, API keys, assistant conversations, users,
   and finally the organization itself.

Render's free tier has no scheduled jobs, so the deletion runs from a
background thread started with the app: once at startup (the server
starts often on the free tier, as it sleeps when idle) and every few
hours while it stays up. A closure that falls due while the server sleeps
runs the next time it wakes."""
import datetime
import logging
import threading
import time
from uuid import UUID

from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

import app.models  # noqa: F401 - every table must be registered before purge_org walks the metadata
from app.core.database import Base, SessionLocal
from app.core.email import send_account_closure_cancelled, send_account_closure_scheduled, send_account_deleted
from app.models.org_settings import OrgSettings
from app.models.organization import Organization
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

CLOSURE_GRACE_DAYS = 90
PURGE_INTERVAL = datetime.timedelta(hours=6)
# langgraph's conversation memory lives in its own tables, keyed by
# "<org_id>:<user_id>:<thread>" (see agent/runner.py) - not in our metadata
_CHECKPOINT_TABLES = ("checkpoint_writes", "checkpoint_blobs", "checkpoints")


class NotOwnerError(Exception):
    pass


class WrongConfirmationError(Exception):
    pass


class NotClosingError(Exception):
    pass


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def business_name(db: Session, org: Organization) -> str:
    org_settings = db.get(OrgSettings, org.id)
    return (org_settings.biz_name if org_settings else None) or org.name


def _team_emails(db: Session, org_id: UUID) -> list[str]:
    return [email for (email,) in db.query(User.email).filter(User.org_id == org_id).all()]


def is_closing(db: Session, org_id: UUID) -> bool:
    org = db.get(Organization, org_id)
    return bool(org and org.closure_scheduled_for)


def status(db: Session, org_id: UUID) -> dict:
    org = db.get(Organization, org_id)
    requested_by = db.get(User, org.closure_requested_by) if org.closure_requested_by else None
    return {
        "business_name": business_name(db, org),
        "closing": org.closure_scheduled_for is not None,
        "requested_at": org.closure_requested_at,
        "scheduled_for": org.closure_scheduled_for,
        "requested_by": requested_by.email if requested_by else None,
        "grace_days": CLOSURE_GRACE_DAYS,
    }


def _normalize(name: str) -> str:
    return " ".join(name.split()).casefold()


def request_closure(db: Session, user: User, confirm_name: str) -> dict:
    if user.role != UserRole.owner:
        raise NotOwnerError()
    org = db.get(Organization, user.org_id)
    name = business_name(db, org)
    if _normalize(confirm_name) != _normalize(name):
        raise WrongConfirmationError(name)
    if org.closure_scheduled_for is None:
        now = _now()
        org.closure_requested_at = now
        org.closure_scheduled_for = now + datetime.timedelta(days=CLOSURE_GRACE_DAYS)
        org.closure_requested_by = user.id
        db.commit()
        for email in _team_emails(db, org.id):
            send_account_closure_scheduled(email, name, org.closure_scheduled_for, user.email)
    return status(db, org.id)


def cancel_closure(db: Session, user: User) -> dict:
    if user.role != UserRole.owner:
        raise NotOwnerError()
    org = db.get(Organization, user.org_id)
    if org.closure_scheduled_for is None:
        raise NotClosingError()
    org.closure_requested_at = org.closure_scheduled_for = org.closure_requested_by = None
    db.commit()
    name = business_name(db, org)
    for email in _team_emails(db, org.id):
        send_account_closure_cancelled(email, name, user.email)
    return status(db, org.id)


# --- the deletion itself --------------------------------------------------------


def _belongs_to_org(table, org_id: UUID):
    """A WHERE clause selecting this table's rows for one organization -
    directly by org_id, or through a foreign key to a table that has one
    (transactions -> customers, auth_tokens -> users, ...). None if the
    table isn't tied to an organization at all."""
    if "org_id" in table.c:
        return table.c.org_id == org_id
    for fk in table.foreign_keys:
        parent = fk.column.table
        if parent.name == "organizations":
            return fk.parent == org_id
        if "org_id" in parent.c:
            return fk.parent.in_(select(fk.column).where(parent.c.org_id == org_id))
    return None


def purge_org(db: Session, org_id: UUID) -> None:
    """Deletes everything belonging to one organization, children before
    parents, in the caller's transaction. Doesn't commit."""
    organizations = Organization.__table__
    for table in reversed(Base.metadata.sorted_tables):
        if table is organizations:
            continue
        condition = _belongs_to_org(table, org_id)
        if condition is not None:
            db.execute(table.delete().where(condition))

    bind = db.get_bind()
    if bind.dialect.name == "postgresql":
        inspector = inspect(bind)
        for name in _CHECKPOINT_TABLES:
            if inspector.has_table(name):
                db.execute(text(f'DELETE FROM "{name}" WHERE thread_id LIKE :prefix'), {"prefix": f"{org_id}:%"})

    db.execute(organizations.delete().where(organizations.c.id == org_id))


def purge_due(db: Session) -> int:
    """Deletes every organization whose closure date has passed. Returns how
    many were deleted. Each one is its own transaction, so one failure
    doesn't hold up the rest."""
    due = db.query(Organization.id).filter(Organization.closure_scheduled_for.isnot(None), Organization.closure_scheduled_for <= _now()).all()
    deleted = 0
    for (org_id,) in due:
        try:
            org = db.get(Organization, org_id)
            name, emails = business_name(db, org), _team_emails(db, org_id)
            db.expunge_all()
            purge_org(db, org_id)
            db.commit()
            deleted += 1
            logger.info("Closed account %s: all data deleted", org_id)
        except Exception:  # noqa: BLE001 - try the others, retry this one next run
            db.rollback()
            logger.exception("Couldn't delete closed account %s - will retry", org_id)
            continue
        for email in emails:
            send_account_deleted(email, name)
    return deleted


_scheduler_started = False


def start_scheduler() -> None:
    global _scheduler_started
    if _scheduler_started:
        return
    _scheduler_started = True

    def loop() -> None:
        while True:
            try:
                with SessionLocal() as db:
                    purge_due(db)
            except Exception:  # noqa: BLE001 - the loop must keep running
                logger.exception("Account closure check failed")
            time.sleep(PURGE_INTERVAL.total_seconds())

    threading.Thread(target=loop, name="account-closure-purge", daemon=True).start()
