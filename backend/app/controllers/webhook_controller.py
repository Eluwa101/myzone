import hashlib
import hmac
import json
import logging
import threading
from uuid import UUID

import httpx
from sqlalchemy.orm import Session

from app.controllers import notification_controller
from app.core.database import SessionLocal
from app.models.webhook import WebhookDelivery, WebhookSubscription, generate_webhook_secret
from app.schemas.webhook import WebhookSubscriptionCreate, WebhookSubscriptionUpdate

logger = logging.getLogger(__name__)

DELIVERY_TIMEOUT_SECONDS = 5
MAX_ATTEMPTS = 2


class WebhookSubscriptionNotFoundError(Exception):
    pass


# --- CRUD ---------------------------------------------------------------


def create_subscription(db: Session, org_id: UUID, data: WebhookSubscriptionCreate) -> WebhookSubscription:
    sub = WebhookSubscription(org_id=org_id, target_url=data.target_url, event_types=data.event_types)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    notification_controller.create_notification(
        db, org_id, "webhook.created", f"New webhook configured for {data.target_url}", link="/webhooks"
    )
    return sub


def list_subscriptions(db: Session, org_id: UUID) -> list[WebhookSubscription]:
    return db.query(WebhookSubscription).filter(WebhookSubscription.org_id == org_id).order_by(WebhookSubscription.created_at.desc()).all()


def _get_subscription(db: Session, org_id: UUID, subscription_id: UUID) -> WebhookSubscription:
    sub = db.query(WebhookSubscription).filter(WebhookSubscription.org_id == org_id, WebhookSubscription.id == subscription_id).first()
    if not sub:
        raise WebhookSubscriptionNotFoundError()
    return sub


def update_subscription(db: Session, org_id: UUID, subscription_id: UUID, data: WebhookSubscriptionUpdate) -> WebhookSubscription:
    sub = _get_subscription(db, org_id, subscription_id)
    if data.target_url is not None:
        sub.target_url = data.target_url
    if data.event_types is not None:
        sub.event_types = data.event_types
    if data.is_active is not None:
        sub.is_active = data.is_active
    if data.regenerate_secret:
        sub.secret = generate_webhook_secret()
    db.commit()
    db.refresh(sub)
    return sub


def delete_subscription(db: Session, org_id: UUID, subscription_id: UUID) -> None:
    sub = _get_subscription(db, org_id, subscription_id)
    db.delete(sub)
    db.commit()


def list_deliveries(db: Session, org_id: UUID, subscription_id: UUID) -> list[WebhookDelivery]:
    _get_subscription(db, org_id, subscription_id)  # raises if not owned by this org
    return (
        db.query(WebhookDelivery)
        .filter(WebhookDelivery.org_id == org_id, WebhookDelivery.subscription_id == subscription_id)
        .order_by(WebhookDelivery.created_at.desc())
        .limit(50)
        .all()
    )


# --- dispatch: called from inside the mutating controllers, never raises ---


def _sign(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def _deliver(org_id: UUID, subscription_id: UUID, target_url: str, secret: str, event_type: str, payload: dict) -> None:
    """Runs on its own thread with its own DB session, so a slow or
    unreachable third-party URL never blocks (or fails) the request that
    triggered the event."""
    body = json.dumps({"event": event_type, "data": payload}, default=str).encode()
    headers = {
        "Content-Type": "application/json",
        "X-MyShop-Signature": _sign(secret, body),
        "X-MyShop-Event": event_type,
    }

    result_status, response_code, attempts = "failed", None, 0
    for attempt in range(1, MAX_ATTEMPTS + 1):
        attempts = attempt
        try:
            resp = httpx.post(target_url, content=body, headers=headers, timeout=DELIVERY_TIMEOUT_SECONDS)
            response_code = resp.status_code
            if resp.is_success:
                result_status = "success"
                break
        except httpx.HTTPError as e:
            logger.info("Webhook delivery to %s failed (attempt %d): %s", target_url, attempt, e)

    db = SessionLocal()
    try:
        db.add(
            WebhookDelivery(
                org_id=org_id,
                subscription_id=subscription_id,
                event_type=event_type,
                payload=payload,
                status=result_status,
                response_code=response_code,
                attempt_count=attempts,
            )
        )
        db.commit()
        if result_status == "success":
            notification_controller.create_notification(
                db, org_id, "webhook.delivery.success", f"Webhook delivered: {event_type}", link="/webhooks"
            )
        else:
            notification_controller.create_notification(
                db,
                org_id,
                "webhook.delivery.failed",
                f"Webhook delivery failed: {event_type}",
                body=f"{target_url} did not accept the delivery after {attempts} attempt(s).",
                link="/webhooks",
            )
    except Exception:  # noqa: BLE001 - logging-only path, must never raise
        logger.exception("Failed to record webhook delivery for subscription %s", subscription_id)
    finally:
        db.close()


def dispatch_event(db: Session, org_id: UUID, event_type: str, payload: dict) -> None:
    try:
        subs = db.query(WebhookSubscription).filter(WebhookSubscription.org_id == org_id, WebhookSubscription.is_active.is_(True)).all()
        for sub in subs:
            if event_type not in (sub.event_types or []):
                continue
            threading.Thread(
                target=_deliver,
                args=(org_id, sub.id, sub.target_url, sub.secret, event_type, payload),
                daemon=True,
            ).start()
    except Exception:  # noqa: BLE001 - a webhook problem must never break the write that triggered it
        logger.exception("Failed to dispatch webhook event %s for org %s", event_type, org_id)


# --- lean, stable payload shapes (deliberately not the full *Out schemas - ---
# --- keeps deliveries small and decoupled from the REST API's own shape) ---


def customer_payload(customer) -> dict:
    return {
        "id": str(customer.id),
        "name": customer.name,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "phone": customer.phone,
        "email": customer.email,
        "status": customer.status.value if customer.status else None,
    }


def order_payload(order) -> dict:
    return {
        "id": str(order.id),
        "customer_id": str(order.customer_id),
        "order_date": order.order_date.isoformat() if order.order_date else None,
        "delivery_date": order.delivery_date.isoformat() if order.delivery_date else None,
        "items": order.items,
        "amount": float(order.amount) if order.amount is not None else None,
        "currency": order.currency,
        "paid": order.paid,
        "delivered": order.delivered,
    }


def transaction_payload(tx) -> dict:
    return {
        "id": str(tx.id),
        "customer_id": str(tx.customer_id),
        "date": tx.date.isoformat() if tx.date else None,
        "item": tx.item,
        "qty": tx.qty,
        "amount": float(tx.amount) if tx.amount is not None else None,
        "currency": tx.currency,
    }


def note_payload(note) -> dict:
    return {
        "id": str(note.id),
        "title": note.title,
        "content": note.content,
        "customer_ids": [str(c.id) for c in note.customers],
    }
