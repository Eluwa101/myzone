from uuid import UUID

from sqlalchemy.orm import Session

from app.models.saved_widget import SavedWidget
from app.schemas.saved_widget import SavedWidgetCreate


class SavedWidgetNotFoundError(Exception):
    pass


def _default_title(question: str) -> str:
    q = question.strip()
    return q if len(q) <= 60 else q[:60].rstrip() + "…"


def create_widget(db: Session, org_id: UUID, user_id: UUID, data: SavedWidgetCreate) -> SavedWidget:
    title = (data.title or "").strip() or _default_title(data.question)
    widget = SavedWidget(org_id=org_id, user_id=user_id, question=data.question.strip(), title=title)
    db.add(widget)
    db.commit()
    db.refresh(widget)
    return widget


def list_widgets(db: Session, org_id: UUID) -> list[SavedWidget]:
    return db.query(SavedWidget).filter(SavedWidget.org_id == org_id).order_by(SavedWidget.created_at).all()


def delete_widget(db: Session, org_id: UUID, widget_id: UUID) -> None:
    widget = db.query(SavedWidget).filter(SavedWidget.org_id == org_id, SavedWidget.id == widget_id).first()
    if not widget:
        raise SavedWidgetNotFoundError()
    db.delete(widget)
    db.commit()
