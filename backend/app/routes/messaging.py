from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.controllers import messaging_controller
from app.core.database import get_db
from app.agent.email_draft import EmailDraftError, draft_email
from app.controllers import segment_controller
from app.controllers.merge_tag_suggestions import describe_segment, suggest_for_segment
from app.core.merge_tags import TAG_PATTERN, available_merge_tags, find_placeholders, merge_tag_problems
from app.models.org_settings import OrgSettings
from app.models.organization import Organization
from app.core.security import get_current_user
from app.models.outbound_message import OutboundMessage
from app.models.user import User
from app.schemas.messaging import (
    EmailDraftOut,
    EmailDraftRequest,
    EmailTemplateCreate,
    EmailTemplateOut,
    EmailTemplateUpdate,
    MergeTagOut,
    MessagePreviewOut,
    MessagePreviewRequest,
    OutboundMessageOut,
    SendEmailRequest,
    SendEmailResult,
    SuggestedMergeTagOut,
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
    return MessagePreviewOut(
        subject=subject,
        body_html=body_html,
        problems=merge_tag_problems(db, current_user.org_id, data.subject, data.body_html),
        placeholders=find_placeholders(data.subject, data.body_html),
    )


def _segment_or_404(db: Session, org_id, segment_id: UUID):
    try:
        return segment_controller.get_segment(db, org_id, segment_id)
    except segment_controller.SegmentNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Segment not found.")


@router.get("/merge-tags/suggested", response_model=list[SuggestedMergeTagOut])
def suggested_merge_tags(segment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    segment = _segment_or_404(db, current_user.org_id, segment_id)
    return suggest_for_segment(db, current_user.org_id, segment)


@router.post("/draft", response_model=EmailDraftOut)
def draft(data: EmailDraftRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    org_id = current_user.org_id
    org = db.get(Organization, org_id)
    org_settings = db.get(OrgSettings, org_id)
    business = [f"Business name: {(org_settings.biz_name if org_settings else None) or org.name}"]
    if org_settings and org_settings.industry:
        business.append(f"Industry: {org_settings.industry}")
    if org_settings and org_settings.manager_name:
        business.append(f"Manager (can sign off): {org_settings.manager_name}")
    business.append(f"Brand colour: {(org_settings.brand_color if org_settings else None) or '#4f46e5'}")

    tags_text = "\n".join(
        f"- {t['tag']} ({t['label']})" for t in available_merge_tags(db, org_id) if TAG_PATTERN.fullmatch(t["tag"])
    )
    segment_text = suggested_text = None
    if data.segment_id:
        segment = _segment_or_404(db, org_id, data.segment_id)
        segment_text = describe_segment(segment)
        suggested_text = "\n".join(f"- {s['label']} ({s['reason']}): {s['tag']}" for s in suggest_for_segment(db, org_id, segment))

    try:
        result = draft_email(
            description=data.description,
            fmt=data.format,
            tags_text=tags_text,
            business_text="\n".join(business),
            segment_text=segment_text,
            suggested_text=suggested_text,
            current_subject=data.current_subject,
            current_body=data.current_body,
            check=lambda subject, body: merge_tag_problems(db, org_id, subject, body),
        )
        return {**result, "placeholders": find_placeholders(result["subject"], result["body_html"])}
    except EmailDraftError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Couldn't write that email - try describing it differently.",
        )


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
