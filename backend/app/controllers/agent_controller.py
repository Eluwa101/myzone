from uuid import UUID

from sqlalchemy.orm import Session

from app.controllers import (
    customer_controller,
    form_controller,
    messaging_controller,
    note_controller,
    notification_controller,
    order_controller,
    segment_controller,
    transaction_controller,
    webhook_controller,
)
from app.models.agent_action import AgentAction
from app.models.pending_action import PendingAction
from app.schemas.customer import CustomerOut
from app.schemas.messaging import SendEmailRequest
from app.schemas.webhook import WebhookSubscriptionCreate


class PendingActionNotFoundError(Exception):
    pass


class UnknownToolError(Exception):
    pass


def log_action(db: Session, org_id: UUID, user_id: UUID, tool_name: str, payload: dict, result: dict) -> None:
    db.add(AgentAction(org_id=org_id, user_id=user_id, tool_name=tool_name, payload=payload, result=result))
    db.commit()


def create_pending_action(db: Session, org_id: UUID, user_id: UUID, tool_name: str, payload: dict, description: str) -> PendingAction:
    pending = PendingAction(org_id=org_id, user_id=user_id, tool_name=tool_name, payload=payload, description=description)
    db.add(pending)
    db.commit()
    db.refresh(pending)
    return pending


def list_pending_actions(db: Session, org_id: UUID) -> list[PendingAction]:
    return db.query(PendingAction).filter(PendingAction.org_id == org_id).order_by(PendingAction.created_at).all()


def _get_pending(db: Session, org_id: UUID, action_id: UUID) -> PendingAction:
    pending = db.query(PendingAction).filter(PendingAction.org_id == org_id, PendingAction.id == action_id).first()
    if not pending:
        raise PendingActionNotFoundError()
    return pending


def get_pending_action(db: Session, org_id: UUID, action_id: UUID) -> PendingAction:
    return _get_pending(db, org_id, action_id)


def reject_pending_action(db: Session, org_id: UUID, action_id: UUID) -> None:
    pending = _get_pending(db, org_id, action_id)
    db.delete(pending)
    db.commit()


# dispatch table: how each destructive tool's payload gets executed once a human confirms it
def _execute_delete_customer(db: Session, org_id: UUID, payload: dict) -> dict:
    customer_controller.delete_customer(db, org_id, UUID(payload["customer_id"]))
    return {"status": "deleted", "customer_id": payload["customer_id"]}


def _execute_merge_customers(db: Session, org_id: UUID, payload: dict) -> dict:
    merged = customer_controller.merge_customers(db, org_id, UUID(payload["keep_id"]), UUID(payload["merge_id"]))
    return {"status": "merged", "customer": CustomerOut.model_validate(merged).model_dump(mode="json")}


def _execute_send_customer_email(db: Session, org_id: UUID, payload: dict) -> dict:
    request = SendEmailRequest(
        customer_ids=[UUID(cid) for cid in payload["customer_ids"]],
        subject=payload["subject"],
        body_html=payload["body_html"],
        template_id=UUID(payload["template_id"]) if payload.get("template_id") else None,
        skip_without_consent=payload.get("skip_without_consent", True),
    )
    result = messaging_controller.send_email_batch(db, org_id, request)
    return {"status": "queued", **result.model_dump(mode="json")}


def _execute_delete_transaction(db: Session, org_id: UUID, payload: dict) -> dict:
    transaction_controller.delete_transaction(db, org_id, UUID(payload["customer_id"]), UUID(payload["transaction_id"]))
    return {"status": "deleted", "transaction_id": payload["transaction_id"]}


def _execute_delete_order(db: Session, org_id: UUID, payload: dict) -> dict:
    order_controller.delete_order(db, org_id, UUID(payload["customer_id"]), UUID(payload["order_id"]))
    return {"status": "deleted", "order_id": payload["order_id"]}


def _execute_delete_note(db: Session, org_id: UUID, payload: dict) -> dict:
    note_controller.delete_note(db, org_id, UUID(payload["note_id"]))
    return {"status": "deleted", "note_id": payload["note_id"]}


def _execute_delete_segment(db: Session, org_id: UUID, payload: dict) -> dict:
    segment_controller.delete_segment(db, org_id, UUID(payload["segment_id"]))
    return {"status": "deleted", "segment_id": payload["segment_id"]}


def _execute_rerun_segment(db: Session, org_id: UUID, payload: dict) -> dict:
    segment = segment_controller.get_segment(db, org_id, UUID(payload["segment_id"]))
    added, removed = segment_controller.refresh_segment(db, segment, "rerun")
    db.refresh(segment)
    return {"status": "updated", "segment": segment.name, "added": added, "removed": removed, "members": segment.member_count}


def _execute_delete_email_template(db: Session, org_id: UUID, payload: dict) -> dict:
    messaging_controller.delete_template(db, org_id, UUID(payload["template_id"]))
    return {"status": "deleted", "template_id": payload["template_id"]}


def _execute_delete_form(db: Session, org_id: UUID, payload: dict) -> dict:
    form_controller.delete_form(db, org_id, UUID(payload["form_id"]))
    return {"status": "deleted", "form_id": payload["form_id"]}


def _execute_delete_webhook(db: Session, org_id: UUID, payload: dict) -> dict:
    webhook_controller.delete_subscription(db, org_id, UUID(payload["webhook_id"]))
    return {"status": "deleted", "webhook_id": payload["webhook_id"]}


def _execute_delete_notification(db: Session, org_id: UUID, payload: dict) -> dict:
    notification_controller.delete_notification(db, org_id, UUID(payload["notification_id"]))
    return {"status": "deleted", "notification_id": payload["notification_id"]}


def _execute_remove_customer_custom_field(db: Session, org_id: UUID, payload: dict) -> dict:
    from app.schemas.customer import CustomerUpdate

    customer = customer_controller.get_customer(db, org_id, UUID(payload["customer_id"]))
    field = payload["field_name"]
    extra = {k: v for k, v in (customer.extra or {}).items() if k != field}
    customer_controller.update_customer(db, org_id, customer.id, CustomerUpdate(extra=extra))
    return {"status": "removed", "customer_id": payload["customer_id"], "field_name": field}


def _execute_create_webhook(db: Session, org_id: UUID, payload: dict) -> dict:
    sub = webhook_controller.create_subscription(
        db, org_id, WebhookSubscriptionCreate(target_url=payload["target_url"], event_types=payload["event_types"])
    )
    # deliberately no secret here: the result is stored in the action log and
    # the model never needs it - it is shown on the Webhooks page
    return {
        "status": "created", "webhook_id": str(sub.id), "target_url": sub.target_url, "event_types": sub.event_types,
        "note": "The signing secret is on the Webhooks page.",
    }


def _execute_import_customers_csv(db: Session, org_id: UUID, payload: dict) -> dict:
    result = customer_controller.import_csv(db, org_id, payload["csv_text"])
    return {"status": "imported", **result.model_dump(mode="json")}


_EXECUTORS = {
    "delete_customer": _execute_delete_customer,
    "merge_customers": _execute_merge_customers,
    "send_customer_email": _execute_send_customer_email,
    "delete_transaction": _execute_delete_transaction,
    "delete_order": _execute_delete_order,
    "delete_note": _execute_delete_note,
    "delete_segment": _execute_delete_segment,
    "rerun_segment": _execute_rerun_segment,
    "delete_email_template": _execute_delete_email_template,
    "delete_form": _execute_delete_form,
    "delete_webhook": _execute_delete_webhook,
    "delete_notification": _execute_delete_notification,
    "remove_customer_custom_field": _execute_remove_customer_custom_field,
    "create_webhook": _execute_create_webhook,
    "import_customers_csv": _execute_import_customers_csv,
}

# The thing a confirmed action pointed at was removed between the request and
# the confirmation (deleted in the UI, or by an earlier confirmation).
_GONE = (
    customer_controller.CustomerNotFoundError,
    transaction_controller.TransactionNotFoundError,
    order_controller.OrderNotFoundError,
    note_controller.NoteNotFoundError,
    segment_controller.SegmentNotFoundError,
    messaging_controller.EmailTemplateNotFoundError,
    form_controller.FormNotFoundError,
    webhook_controller.WebhookSubscriptionNotFoundError,
    notification_controller.NotificationNotFoundError,
)


def confirm_pending_action(db: Session, org_id: UUID, user_id: UUID, action_id: UUID) -> dict:
    pending = _get_pending(db, org_id, action_id)
    executor = _EXECUTORS.get(pending.tool_name)
    if not executor:
        raise UnknownToolError(pending.tool_name)

    try:
        result = executor(db, org_id, pending.payload)
    except _GONE:
        # nothing left to act on - drop the stale request rather than 500 on every retry
        db.rollback()
        db.delete(pending)
        db.commit()
        return {"status": "error", "message": "That record no longer exists, so nothing was changed."}
    log_action(db, org_id, user_id, pending.tool_name, pending.payload, result)
    db.delete(pending)
    db.commit()
    return result
