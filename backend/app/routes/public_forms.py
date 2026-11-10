"""Unauthenticated endpoints, reachable by anyone holding a form's
public_token - the hosted public form page, and any third-party
integration (Zapier, a Google Form's Apps Script trigger, a plain curl/
webhook) that wants to push data into this org's customer list directly.
submit_form accepts arbitrary JSON (not just string fields) and, when the
form has signing enabled, verifies an HMAC-SHA256 X-Signature header over
the raw body - so this endpoint doubles as a real machine-to-machine
incoming webhook, not just a human form target."""
import json

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.controllers import form_controller
from app.core.database import get_db
from app.core.rate_limit import check_rate_limit
from app.schemas.form import FormSubmitResult, PublicFormOut

router = APIRouter(prefix="/api/public/forms", tags=["public-forms"])


@router.get("/{token}", response_model=PublicFormOut)
def get_public_form(token: str, db: Session = Depends(get_db)):
    try:
        form = form_controller.get_public_form(db, token)
    except form_controller.FormNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")
    business_name = form_controller.get_public_form_business_name(db, form)
    return PublicFormOut(name=form.name, fields=form.fields, business_name=business_name)


@router.post("/{token}/submit", response_model=FormSubmitResult)
async def submit_form(token: str, request: Request, db: Session = Depends(get_db)):
    if not check_rate_limit(token):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many submissions - please try again shortly.")

    raw_body = await request.body()
    try:
        payload = json.loads(raw_body) if raw_body else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body.")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Payload must be a JSON object.")

    try:
        _submission, created, tx_logged, order_logged = form_controller.submit_public_form(
            db, token, payload, raw_body, request.headers.get("x-signature")
        )
    except form_controller.FormNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form not found.")
    except form_controller.InvalidSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing X-Signature header.")
    except form_controller.MissingRequiredFieldsError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Missing required field(s): {', '.join(e.missing)}")
    return FormSubmitResult(status="ok", customer_created=created, transaction_logged=tx_logged, order_logged=order_logged)
