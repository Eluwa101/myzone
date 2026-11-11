from uuid import UUID

from sqlalchemy.orm import Session

from app.controllers import customer_controller, messaging_controller
from app.models.agent_action import AgentAction
from app.models.pending_action import PendingAction
from app.schemas.customer import CustomerOut
from app.schemas.messaging import SendEmailRequest


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


_EXECUTORS = {
    "delete_customer": _execute_delete_customer,
    "merge_customers": _execute_merge_customers,
    "send_customer_email": _execute_send_customer_email,
}


def confirm_pending_action(db: Session, org_id: UUID, user_id: UUID, action_id: UUID) -> dict:
    pending = _get_pending(db, org_id, action_id)
    executor = _EXECUTORS.get(pending.tool_name)
    if not executor:
        raise UnknownToolError(pending.tool_name)

    result = executor(db, org_id, pending.payload)
    log_action(db, org_id, user_id, pending.tool_name, pending.payload, result)
    db.delete(pending)
    db.commit()
    return result
