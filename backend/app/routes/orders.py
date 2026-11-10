from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.controllers import customer_controller, order_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.order import OrderCreate, OrderOut, OrderUpdate, OrderWithCustomerOut

router = APIRouter(prefix="/api/customers/{customer_id}/orders", tags=["orders"])

all_orders_router = APIRouter(prefix="/api/orders", tags=["orders"])


@all_orders_router.get("", response_model=list[OrderWithCustomerOut])
def list_all_orders(
    pending: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    orders = order_controller.list_all_orders(db, current_user.org_id, pending_only=pending)
    return [
        OrderWithCustomerOut(
            id=o.id,
            customer_id=o.customer_id,
            customer_name=o.customer.name,
            order_date=o.order_date,
            delivery_date=o.delivery_date,
            items=o.items,
            amount=o.amount,
            currency=o.currency,
            paid=o.paid,
            delivered=o.delivered,
            notes=o.notes,
        )
        for o in orders
    ]


@router.get("", response_model=list[OrderOut])
def list_orders(
    customer_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return order_controller.list_orders(db, current_user.org_id, customer_id)
    except customer_controller.CustomerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")


@router.post("", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
def create_order(
    customer_id: UUID,
    data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return order_controller.create_order(db, current_user.org_id, customer_id, data)
    except customer_controller.CustomerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")


@router.patch("/{order_id}", response_model=OrderOut)
def update_order(
    customer_id: UUID,
    order_id: UUID,
    data: OrderUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return order_controller.update_order(db, current_user.org_id, customer_id, order_id, data)
    except (customer_controller.CustomerNotFoundError, order_controller.OrderNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")


@router.delete("/{order_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_order(
    customer_id: UUID,
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        order_controller.delete_order(db, current_user.org_id, customer_id, order_id)
    except (customer_controller.CustomerNotFoundError, order_controller.OrderNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
