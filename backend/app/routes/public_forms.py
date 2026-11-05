"""Unauthenticated endpoints, reachable by anyone holding a form's
public_token - the hosted public form page, and any third-party
integration (Zapier, a Google Form's Apps Script trigger, a plain curl/
webhook) that wants to push data into this org's customer list directly."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.controllers import form_controller
from app.core.database import get_db
from app.core.rate_limit import check_rate_limit
from app.schemas.form import FormSubmitResult, PublicFormOut

router = APIRouter(prefix="/api/public/forms", tags=["public-forms"])


@router.get("/{token}", response_model=PublicFormOut)
def get_public_form(token: str, db: Session = Depends(get_db)):
    try:
        return form_controller.get_public_form(db, token)
    except form_controller.FormNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")


@router.post("/{token}/submit", response_model=FormSubmitResult)
def submit_form(token: str, payload: dict[str, str], db: Session = Depends(get_db)):
    if not check_rate_limit(token):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many submissions - please try again shortly.")
    try:
        _submission, created, tx_logged = form_controller.submit_public_form(db, token, payload)
    except form_controller.FormNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")
    except form_controller.MissingRequiredFieldsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Missing required field(s): {', '.join(e.missing)}")
    return FormSubmitResult(status="ok", customer_created=created, transaction_logged=tx_logged)
