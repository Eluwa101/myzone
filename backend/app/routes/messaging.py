import html
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.controllers import messaging_controller
from app.core.database import get_db
from app.core.paging import paginate
from app.agent.email_draft import EmailDraftError, draft_email
from app.agent.rewrite import RewriteError, build_rewrite_context, rewrite_message
from app.controllers import segment_controller
from app.controllers.merge_tag_suggestions import describe_segment, suggest_for_segment
from app.core.merge_tags import TAG_PATTERN, available_merge_tags, find_placeholders, merge_tag_problems
from app.models.org_settings import OrgSettings
from app.models.organization import Organization
from app.core.security import get_current_user
from app.models.outbound_message import MessageChannel, MessageStatus, OutboundMessage
from app.models.user import User
from app.schemas.messaging import (
    EmailDraftOut,
    EmailDraftRequest,
    EmailTemplateCreate,
    EmailTemplateOut,
    EmailTemplateUpdate,
    MergeTagOut,
    MessagePreviewBatchItem,
    MessagePreviewBatchOut,
    MessagePreviewBatchRequest,
    MessagePreviewOut,
    MessagePreviewRequest,
    RewriteOut,
    RewriteRequest,
    OutboundMessageDetailOut,
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
def list_templates(
    response: Response,
    search: str | None = None,
    page: int | None = None,
    page_size: int = 20,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return paginate(messaging_controller.query_templates(db, current_user.org_id, search), response, page, page_size)


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


@router.post("/preview-batch", response_model=MessagePreviewBatchOut)
def preview_batch(data: MessagePreviewBatchRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """The same merge-tag resolution as /preview, for up to 50 customers at once
    - used to fill a page of WhatsApp chats in one request."""
    previews, missing = [], []
    for customer_id in dict.fromkeys(data.customer_ids):
        result = messaging_controller.preview(db, current_user.org_id, customer_id, data.subject, data.body_html)
        if result is None:
            missing.append(customer_id)
        else:
            previews.append(MessagePreviewBatchItem(customer_id=customer_id, subject=result[0], body_html=result[1]))
    return MessagePreviewBatchOut(
        previews=previews,
        problems=merge_tag_problems(db, current_user.org_id, data.subject, data.body_html),
        placeholders=find_placeholders(data.subject, data.body_html),
        missing=missing,
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


@router.post("/rewrite", response_model=RewriteOut)
def rewrite(data: RewriteRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Shorten, reformat, make friendlier or rewrite a message that is already written.
    With keep_merge_tags on, every merge tag is guaranteed to come back as it went in -
    otherwise the original is returned with a warning, never a damaged message."""
    org_id = current_user.org_id
    business_text, tags_text = build_rewrite_context(db, org_id)
    try:
        result = rewrite_message(
            channel=data.channel, action=data.action, body=data.body, subject=data.subject, instruction=data.instruction,
            keep_merge_tags=data.keep_merge_tags, tags_text=tags_text, business_text=business_text,
            check=lambda subject, body: merge_tag_problems(db, org_id, subject, body),
        )
    except RewriteError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(e).capitalize() + ".")
    return {**result, "placeholders": find_placeholders(result["subject"] or "", result["body"])}


@router.post("/send", response_model=SendEmailResult)
def send(data: SendEmailRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    if data.template_id:
        try:
            messaging_controller.get_template(db, current_user.org_id, data.template_id)
        except messaging_controller.EmailTemplateNotFoundError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Template not found.")
    return messaging_controller.send_email_batch(db, current_user.org_id, data)


def _preview(body: str, length: int = 160) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body or "", flags=re.IGNORECASE | re.DOTALL)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def _message_out(m: OutboundMessage, with_body: bool = False):
    fields = dict(
        id=m.id,
        customer_id=m.customer_id,
        customer_name=m.customer.name if m.customer else None,
        channel=m.channel.value,
        status=m.status.value,
        subject=m.subject,
        body_preview=_preview(m.body),
        error=m.error,
        created_at=m.created_at,
    )
    return OutboundMessageDetailOut(**fields, body=m.body) if with_body else OutboundMessageOut(**fields)


@router.get("/history", response_model=list[OutboundMessageOut])
def history(
    response: Response,
    customer_id: UUID | None = None,
    channel: MessageChannel | None = None,
    status_filter: MessageStatus | None = Query(default=None, alias="status"),
    search: str | None = None,
    page: int | None = None,
    page_size: int = 20,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = messaging_controller.query_history(db, current_user.org_id, customer_id, channel, status_filter, search)
    # without ?page= the old "most recent `limit`" behaviour is kept
    return [_message_out(m) for m in paginate(q, response, page, page_size, limit=limit)]


@router.get("/history/{message_id}", response_model=OutboundMessageDetailOut)
def history_detail(message_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return _message_out(messaging_controller.get_history_message(db, current_user.org_id, message_id), with_body=True)
    except messaging_controller.OutboundMessageNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found.")
