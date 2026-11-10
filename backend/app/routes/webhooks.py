from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.controllers import webhook_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.webhook import (
    EVENT_TYPES,
    WebhookDeliveryOut,
    WebhookSubscriptionCreate,
    WebhookSubscriptionOut,
    WebhookSubscriptionUpdate,
)

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])


@router.get("/event-types", response_model=list[str])
def list_event_types():
    return sorted(EVENT_TYPES)


@router.get("", response_model=list[WebhookSubscriptionOut])
def list_subscriptions(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return webhook_controller.list_subscriptions(db, current_user.org_id)


@router.post("", response_model=WebhookSubscriptionOut, status_code=status.HTTP_201_CREATED)
def create_subscription(data: WebhookSubscriptionCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return webhook_controller.create_subscription(db, current_user.org_id, data)


@router.patch("/{subscription_id}", response_model=WebhookSubscriptionOut)
def update_subscription(
    subscription_id: UUID,
    data: WebhookSubscriptionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return webhook_controller.update_subscription(db, current_user.org_id, subscription_id, data)
    except webhook_controller.WebhookSubscriptionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")


@router.delete("/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_subscription(subscription_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        webhook_controller.delete_subscription(db, current_user.org_id, subscription_id)
    except webhook_controller.WebhookSubscriptionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{subscription_id}/deliveries", response_model=list[WebhookDeliveryOut])
def list_deliveries(subscription_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        return webhook_controller.list_deliveries(db, current_user.org_id, subscription_id)
    except webhook_controller.WebhookSubscriptionNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook subscription not found.")
