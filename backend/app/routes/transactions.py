from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.controllers import customer_controller, transaction_controller
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.schemas.transaction import TransactionCreate, TransactionOut, TransactionUpdate

router = APIRouter(prefix="/api/customers/{customer_id}/transactions", tags=["transactions"])


@router.post("", response_model=TransactionOut, status_code=status.HTTP_201_CREATED)
def add_transaction(
    customer_id: UUID,
    data: TransactionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return transaction_controller.add_transaction(db, current_user.org_id, customer_id, data)
    except customer_controller.CustomerNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found.")


@router.patch("/{transaction_id}", response_model=TransactionOut)
def update_transaction(
    customer_id: UUID,
    transaction_id: UUID,
    data: TransactionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return transaction_controller.update_transaction(db, current_user.org_id, customer_id, transaction_id, data)
    except (customer_controller.CustomerNotFoundError, transaction_controller.TransactionNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    customer_id: UUID,
    transaction_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        transaction_controller.delete_transaction(db, current_user.org_id, customer_id, transaction_id)
    except (customer_controller.CustomerNotFoundError, transaction_controller.TransactionNotFoundError):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
