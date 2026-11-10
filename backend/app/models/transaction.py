import datetime
import uuid

from sqlalchemy import Date, DateTime, ForeignKey, JSON, Numeric, String, Uuid as UUID, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Transaction(Base):
    """One checkout/sale event for a customer. `items` holds every line
    recorded together (e.g. several products bought in the same visit) as
    [{"item": str, "qty": float, "amount": float}, ...] - each line's
    `amount` is that line's own total price (not a unit price), matching
    what the UI's per-line "Amount" field always meant. `amount` on the
    transaction itself is the sum of the lines' amounts, kept as a real
    column so sorting/aggregating doesn't need to unpack JSON every time."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("customers.id"), index=True)

    date: Mapped[datetime.date] = mapped_column(Date)
    items: Mapped[list] = mapped_column(JSON, default=list)
    amount: Mapped[float] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(3), default="")

    created_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    customer = relationship("Customer", back_populates="transactions")
