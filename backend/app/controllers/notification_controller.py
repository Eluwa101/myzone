import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.notification import Notification

logger = logging.getLogger(__name__)


class NotificationNotFoundError(Exception):
    pass


def create_notification(db: Session, org_id: UUID, type: str, title: str, body: str | None = None, link: str | None = None) -> None:
    """Called from inside the controllers that already know an event
    happened (order created, webhook delivered, CSV imported, form
    submitted, assistant unavailable) - never raises, so a notification-
    logging problem can never break the real operation it's attached to."""
    try:
        db.add(Notification(org_id=org_id, type=type, title=title, body=body, link=link))
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()
        logger.exception("Failed to create notification (type=%s) for org %s", type, org_id)


def list_notifications(db: Session, org_id: UUID, limit: int = 50) -> list[Notification]:
    return db.query(Notification).filter(Notification.org_id == org_id).order_by(Notification.created_at.desc()).limit(limit).all()


def unread_count(db: Session, org_id: UUID) -> int:
    return db.query(Notification).filter(Notification.org_id == org_id, Notification.read.is_(False)).count()


def _get_notification(db: Session, org_id: UUID, notification_id: UUID) -> Notification:
    notification = db.query(Notification).filter(Notification.org_id == org_id, Notification.id == notification_id).first()
    if not notification:
        raise NotificationNotFoundError()
    return notification


def mark_read(db: Session, org_id: UUID, notification_id: UUID) -> Notification:
    notification = _get_notification(db, org_id, notification_id)
    notification.read = True
    db.commit()
    db.refresh(notification)
    return notification


def mark_all_read(db: Session, org_id: UUID) -> int:
    updated = (
        db.query(Notification)
        .filter(Notification.org_id == org_id, Notification.read.is_(False))
        .update({"read": True}, synchronize_session=False)
    )
    db.commit()
    return updated
