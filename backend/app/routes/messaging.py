from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.controllers import messaging_controller
from app.core.database import get_db
from app.core.merge_tags import available_merge_tags
from app.core.security import get_current_user
from app.models.outbound_message import OutboundMessage
from app.models.user import User
from app.schemas.messaging import (
    EmailTemplateCreate,
    EmailTemplateOut,
    EmailTemplateUpdate,
    MergeTagOut,
    MessagePreviewOut,
    MessagePreviewRequest,
    OutboundMessageOut,
    SendEmailRequest,
    SendEmailResult,
)

router = APIRouter(prefix="/api/messages", tags=["messaging"])


@router.get("/merge-tags", response_model=list[MergeTagOut])
def list_merge_tags(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return available_merge_tags(db, current_user.org_id)


@router.get("/templates", response_model=list[EmailTemplateOut])
def list_templates(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return messaging_controller.list_templates(db, current_user.org_id)


@router.post("/templates", response_model=EmailTemplateOut, status_code=status.HTTP_201_CREATED)
def create_template(data: EmailTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return messaging_controller.create_template(db, current_user.org_id, data)


@router.patch("/templates/{template_id}", response_model=EmailTemplateOut)
def update_template(
    template_id: UUID, data: EmailTemplateUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    try:
        return messaging_controller.update_template(db, current_user.org_id, template_id, data)
    except messaging_controller.EmailTemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_template(template_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        messaging_controller.delete_template(db, current_user.org_id, template_id)
    except messaging_controller.EmailTemplateNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")


@router.post("/preview", response_model=MessagePreviewOut)
def preview(data: MessagePreviewRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    result = messaging_controller.preview(db, current_user.org_id, data.customer_id, data.subject, data.body_html)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No customer with that id.")
    subject, body_html = result
    return MessagePreviewOut(subject=subject, body_html=body_html)


@router.post("/send", response_model=SendEmailResult)
def send(data: SendEmailRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if data.template_id:
        try:
            messaging_controller.get_template(db, current_user.org_id, data.template_id)
        except messaging_controller.EmailTemplateNotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    return messaging_controller.send_email_batch(db, current_user.org_id, data)


@router.get("/history", response_model=list[OutboundMessageOut])
def history(
    customer_id: UUID | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(OutboundMessage).filter(OutboundMessage.org_id == current_user.org_id)
    if customer_id:
        q = q.filter(OutboundMessage.customer_id == customer_id)
    return q.order_by(OutboundMessage.created_at.desc()).limit(limit).all()
