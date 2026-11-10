from uuid import UUID

from sqlalchemy.orm import Session, joinedload

from app.controllers import notification_controller, webhook_controller
from app.controllers.customer_controller import get_customer
from app.models.order import Order
from app.schemas.order import OrderCreate, OrderUpdate


class OrderNotFoundError(Exception):
    pass


def create_order(db: Session, org_id: UUID, customer_id: UUID, data: OrderCreate) -> Order:
    customer = get_customer(db, org_id, customer_id)
    order = Order(
        org_id=org_id,
        customer_id=customer.id,
        order_date=data.order_date,
        delivery_date=data.delivery_date,
        items=[item.model_dump() for item in data.items],
        amount=data.amount,
        currency=data.currency,
        paid=data.paid,
        delivered=data.delivered,
        notes=data.notes,
    )
    db.add(order)
    db.commit()
    db.refresh(order)
    webhook_controller.dispatch_event(db, org_id, "order.created", webhook_controller.order_payload(order))
    notification_controller.create_notification(
        db, org_id, "order.created", f"New order for {customer.name}", link=f"/customers/{customer.id}?tab=orders"
    )
    return order


def list_orders(db: Session, org_id: UUID, customer_id: UUID) -> list[Order]:
    get_customer(db, org_id, customer_id)
    return (
        db.query(Order)
        .filter(Order.org_id == org_id, Order.customer_id == customer_id)
        .order_by(Order.order_date.desc())
        .all()
    )


def list_all_orders(db: Session, org_id: UUID, pending_only: bool = False) -> list[Order]:
    q = db.query(Order).options(joinedload(Order.customer)).filter(Order.org_id == org_id)
    if pending_only:
        q = q.filter(Order.delivered.is_(False))
    return q.order_by(Order.order_date.desc()).all()


def _get_order(db: Session, org_id: UUID, customer_id: UUID, order_id: UUID) -> Order:
    get_customer(db, org_id, customer_id)
    order = (
        db.query(Order)
        .filter(Order.org_id == org_id, Order.customer_id == customer_id, Order.id == order_id)
        .first()
    )
    if not order:
        raise OrderNotFoundError()
    return order


def update_order(db: Session, org_id: UUID, customer_id: UUID, order_id: UUID, data: OrderUpdate) -> Order:
    order = _get_order(db, org_id, customer_id, order_id)
    updates = data.model_dump(exclude_unset=True)
    if "items" in updates:
        updates["items"] = [item if isinstance(item, dict) else item.model_dump() for item in updates["items"]]
    for field, value in updates.items():
        setattr(order, field, value)
    db.commit()
    db.refresh(order)
    webhook_controller.dispatch_event(db, org_id, "order.updated", webhook_controller.order_payload(order))
    return order


def delete_order(db: Session, org_id: UUID, customer_id: UUID, order_id: UUID) -> None:
    order = _get_order(db, org_id, customer_id, order_id)
    payload = webhook_controller.order_payload(order)
    db.delete(order)
    db.commit()
    webhook_controller.dispatch_event(db, org_id, "order.deleted", payload)
