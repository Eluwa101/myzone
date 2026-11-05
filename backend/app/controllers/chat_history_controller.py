from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread


class ThreadNotFoundError(Exception):
    pass


def _title_from(message: str) -> str:
    message = message.strip()
    if not message:
        return "New chat"
    return message[:60] + ("…" if len(message) > 60 else "")


def record_user_message(db: Session, org_id: UUID, user_id: UUID, thread_id: str, message: str, has_image: bool = False) -> ChatThread:
    thread = db.get(ChatThread, thread_id)
    if not thread or thread.org_id != org_id or thread.user_id != user_id:
        thread = ChatThread(id=thread_id, org_id=org_id, user_id=user_id, title=_title_from(message))
        db.add(thread)
        db.flush()
    db.add(ChatMessage(thread_id=thread.id, role="user", content=message, has_image=has_image))
    db.commit()
    return thread


def record_assistant_message(db: Session, thread_id: str, content: str) -> None:
    db.add(ChatMessage(thread_id=thread_id, role="assistant", content=content))
    thread = db.get(ChatThread, thread_id)
    if thread:
        thread.updated_at = datetime.now(timezone.utc)
    db.commit()


def list_threads(db: Session, org_id: UUID, user_id: UUID) -> list[ChatThread]:
    return (
        db.query(ChatThread)
        .filter(ChatThread.org_id == org_id, ChatThread.user_id == user_id)
        .order_by(ChatThread.updated_at.desc())
        .all()
    )


def get_thread_messages(db: Session, org_id: UUID, user_id: UUID, thread_id: str) -> list[ChatMessage]:
    thread = (
        db.query(ChatThread)
        .options(joinedload(ChatThread.messages))
        .filter(ChatThread.id == thread_id, ChatThread.org_id == org_id, ChatThread.user_id == user_id)
        .first()
    )
    if not thread:
        raise ThreadNotFoundError()
    return thread.messages


def delete_thread(db: Session, org_id: UUID, user_id: UUID, thread_id: str) -> None:
    thread = db.query(ChatThread).filter(ChatThread.id == thread_id, ChatThread.org_id == org_id, ChatThread.user_id == user_id).first()
    if not thread:
        raise ThreadNotFoundError()
    db.delete(thread)
    db.commit()
