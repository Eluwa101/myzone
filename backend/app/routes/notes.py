from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.controllers import note_controller
from app.core.database import get_db
from app.core.paging import paginate
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.note import NoteCreate, NoteOut, NoteUpdate

router = APIRouter(prefix="/api/notes", tags=["notes"])


@router.get("", response_model=list[NoteOut])
def list_notes(
    response: Response,
    customer_id: UUID | None = None,
    pending: bool = False,
    search: str | None = None,
    page: int | None = None,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = note_controller.query_notes(db, current_user.org_id, customer_id, pending, search)
    return paginate(q, response, page, page_size)


@router.get("/pending/count")
def pending_count(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return {"count": note_controller.count_pending(db, current_user.org_id)}


@router.get("/{note_id}", response_model=NoteOut)
def get_note(note_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return note_controller.get_note(db, current_user.org_id, note_id)
    except note_controller.NoteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found.")


@router.post("", response_model=NoteOut, status_code=status.HTTP_201_CREATED)
def create_note(data: NoteCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return note_controller.create_note(db, current_user.org_id, data)


@router.patch("/{note_id}", response_model=NoteOut)
def update_note(
    note_id: UUID,
    data: NoteUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return note_controller.update_note(db, current_user.org_id, note_id, data)
    except note_controller.NoteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found.")


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(note_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        note_controller.delete_note(db, current_user.org_id, note_id)
    except note_controller.NoteNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
