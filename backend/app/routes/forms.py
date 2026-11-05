from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.controllers import form_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.form import FormCreate, FormOut, FormSubmissionOut, FormUpdate

router = APIRouter(prefix="/api/forms", tags=["forms"])


@router.get("", response_model=list[FormOut])
def list_forms(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return form_controller.list_forms(db, current_user.org_id)


@router.post("", response_model=FormOut, status_code=status.HTTP_201_CREATED)
def create_form(data: FormCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return form_controller.create_form(db, current_user.org_id, data)


@router.get("/{form_id}", response_model=FormOut)
def get_form(form_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return form_controller.get_form(db, current_user.org_id, form_id)
    except form_controller.FormNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")


@router.patch("/{form_id}", response_model=FormOut)
def update_form(
    form_id: UUID,
    data: FormUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return form_controller.update_form(db, current_user.org_id, form_id, data)
    except form_controller.FormNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")


@router.delete("/{form_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_form(form_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        form_controller.delete_form(db, current_user.org_id, form_id)
    except form_controller.FormNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{form_id}/submissions", response_model=list[FormSubmissionOut])
def list_submissions(form_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return form_controller.list_submissions(db, current_user.org_id, form_id)
    except form_controller.FormNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")
