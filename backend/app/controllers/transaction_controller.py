from uuid import UUID

from sqlalchemy.orm import Session

from app.controllers import webhook_controller
from app.controllers.customer_controller import get_customer, recompute_derived_fields
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate, TransactionItem, TransactionUpdate


class TransactionNotFoundError(Exception):
    pass


def _items_total(items: list[TransactionItem]) -> float:
    return sum(float(i.amount) for i in items)


def add_transaction(db: Session, org_id: UUID, customer_id: UUID, data: TransactionCreate) -> Transaction:
    customer = get_customer(db, org_id, customer_id)
    tx = Transaction(
        customer_id=customer.id,
        date=data.date,
        items=[i.model_dump() for i in data.items],
        amount=_items_total(data.items),
        currency=data.currency,
    )
    customer.transactions.append(tx)
    recompute_derived_fields(customer)
    db.commit()
    db.refresh(tx)
    webhook_controller.dispatch_event(db, org_id, "transaction.created", webhook_controller.transaction_payload(tx))
    return tx


def get_transaction(db: Session, org_id: UUID, customer_id: UUID, transaction_id: UUID) -> Transaction:
    customer = get_customer(db, org_id, customer_id)
    for tx in customer.transactions:
        if tx.id == transaction_id:
            return tx
    raise TransactionNotFoundError()


def update_transaction(db: Session, org_id: UUID, customer_id: UUID, transaction_id: UUID, data: TransactionUpdate) -> Transaction:
    tx = get_transaction(db, org_id, customer_id, transaction_id)
    updates = data.model_dump(exclude_unset=True)
    if "items" in updates and updates["items"] is not None:
        tx.items = updates.pop("items")
        tx.amount = sum(float(i["amount"]) for i in tx.items)
    for field, value in updates.items():
        setattr(tx, field, value)
    customer = get_customer(db, org_id, customer_id)
    recompute_derived_fields(customer)
    db.commit()
    db.refresh(tx)
    webhook_controller.dispatch_event(db, org_id, "transaction.updated", webhook_controller.transaction_payload(tx))
    return tx


def delete_transaction(db: Session, org_id: UUID, customer_id: UUID, transaction_id: UUID) -> None:
    tx = get_transaction(db, org_id, customer_id, transaction_id)
    payload = webhook_controller.transaction_payload(tx)
    db.delete(tx)
    db.flush()
    customer = get_customer(db, org_id, customer_id)
    recompute_derived_fields(customer)
    db.commit()
    webhook_controller.dispatch_event(db, org_id, "transaction.deleted", payload)
