from uuid import UUID

from sqlalchemy.orm import Session

from app.controllers.customer_controller import get_customer, recompute_derived_fields
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate, TransactionUpdate


class TransactionNotFoundError(Exception):
    pass


def add_transaction(db: Session, org_id: UUID, customer_id: UUID, data: TransactionCreate) -> Transaction:
    customer = get_customer(db, org_id, customer_id)
    tx = Transaction(customer_id=customer.id, date=data.date, item=data.item, qty=data.qty, amount=data.amount, currency=data.currency)
    customer.transactions.append(tx)
    recompute_derived_fields(customer)
    db.commit()
    db.refresh(tx)
    return tx


def _get_transaction(db: Session, org_id: UUID, customer_id: UUID, transaction_id: UUID) -> Transaction:
    customer = get_customer(db, org_id, customer_id)
    for tx in customer.transactions:
        if tx.id == transaction_id:
            return tx
    raise TransactionNotFoundError()


def update_transaction(db: Session, org_id: UUID, customer_id: UUID, transaction_id: UUID, data: TransactionUpdate) -> Transaction:
    tx = _get_transaction(db, org_id, customer_id, transaction_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(tx, field, value)
    customer = get_customer(db, org_id, customer_id)
    recompute_derived_fields(customer)
    db.commit()
    db.refresh(tx)
    return tx


def delete_transaction(db: Session, org_id: UUID, customer_id: UUID, transaction_id: UUID) -> None:
    tx = _get_transaction(db, org_id, customer_id, transaction_id)
    db.delete(tx)
    db.flush()
    customer = get_customer(db, org_id, customer_id)
    recompute_derived_fields(customer)
    db.commit()
