"""
Builds the set of tools handed to the agent for one request. Tools are
built fresh per-request (closures over this request's db session, org_id,
user_id) rather than as global singletons, so there's no risk of one
org's agent call leaking another org's db session or scope.

Every tool validates its arguments via the function's type hints (LangChain
builds a Pydantic schema from them before the function body ever runs) and
calls the *same* controller functions the REST API uses - one code path for
agent writes and UI writes.

Reversible tools (create/update/log a transaction) execute immediately.
Destructive tools (delete_customer, merge_customers) never mutate anything
directly: they create a PendingAction row and return a confirm_required
payload. A human must call the /api/agent/pending/{id}/confirm endpoint
before the action actually runs.
"""
from uuid import UUID

from langchain.tools import tool
from sqlalchemy.orm import Session

from app.controllers import agent_controller, customer_controller, note_controller, order_controller, transaction_controller
from app.models.customer import CustomerStatus
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.schemas.note import NoteCreate
from app.schemas.order import OrderCreate, OrderItem
from app.schemas.transaction import TransactionCreate, TransactionUpdate


def _clean(value: str) -> str | None:
    return value.strip() if value and value.strip() else None


def _serialize_customer(customer) -> dict:
    from app.schemas.customer import CustomerOut

    return CustomerOut.model_validate(customer).model_dump(mode="json")


def build_tools(db: Session, org_id: UUID, user_id: UUID) -> list:
    def log(tool_name: str, payload: dict, result: dict) -> None:
        agent_controller.log_action(db, org_id, user_id, tool_name, payload, result)

    @tool
    def create_customer(
        name: str,
        phone: str = "",
        email: str = "",
        job: str = "",
        nationality: str = "",
        pet: str = "",
        address: str = "",
        notes: str = "",
        interests: str = "",
    ) -> dict:
        """Create a new customer record. If a likely-duplicate already exists
        (matched by phone, email, or name), this returns {"status": "conflict"}
        instead of creating anything - tell the user about the existing
        customer and ask whether to update it (use update_customer) or save
        this as a separate new customer anyway (use create_customer_as_new,
        same arguments)."""
        data = CustomerCreate(
            name=name, phone=_clean(phone), email=_clean(email), job=_clean(job),
            nationality=_clean(nationality), pet=_clean(pet), address=_clean(address),
            notes=_clean(notes), interests=_clean(interests),
        )
        try:
            customer = customer_controller.create_customer(db, org_id, data)
        except customer_controller.DuplicateCustomerError as e:
            result = {"status": "conflict", "existing_id": str(e.existing.id), "existing_name": e.existing.name}
            log("create_customer", data.model_dump(), result)
            return result
        # "action" (not "status") - the customer's own lifecycle status
        # (lead/customer/inactive) is already a field in the spread dict below,
        # and a same-named wrapper key would silently clobber it.
        result = {"action": "created", **_serialize_customer(customer)}
        log("create_customer", data.model_dump(), result)
        return result

    @tool
    def create_customer_as_new(
        name: str,
        phone: str = "",
        email: str = "",
        job: str = "",
        nationality: str = "",
        pet: str = "",
        address: str = "",
        notes: str = "",
        interests: str = "",
    ) -> dict:
        """Create a new customer record even if it looks like a duplicate of
        an existing one. Only use this after create_customer returned a
        conflict and the user confirmed they want a separate record anyway."""
        data = CustomerCreate(
            name=name, phone=_clean(phone), email=_clean(email), job=_clean(job),
            nationality=_clean(nationality), pet=_clean(pet), address=_clean(address),
            notes=_clean(notes), interests=_clean(interests),
        )
        customer = customer_controller.create_customer(db, org_id, data, force=True)
        result = {"action": "created", **_serialize_customer(customer)}
        log("create_customer_as_new", data.model_dump(), result)
        return result

    @tool
    def update_customer(
        customer_id: str,
        name: str = "",
        phone: str = "",
        email: str = "",
        job: str = "",
        nationality: str = "",
        pet: str = "",
        address: str = "",
        notes: str = "",
        interests: str = "",
        status: str = "",
    ) -> dict:
        """Update fields on an existing customer. Only pass the fields that
        should change - leave others blank. status, if given, must be one of
        lead, customer, inactive."""
        fields = {
            "name": _clean(name), "phone": _clean(phone), "email": _clean(email), "job": _clean(job),
            "nationality": _clean(nationality), "pet": _clean(pet), "address": _clean(address),
            "notes": _clean(notes), "interests": _clean(interests),
        }
        updates = {k: v for k, v in fields.items() if v is not None}
        if status.strip():
            try:
                updates["status"] = CustomerStatus(status.strip().lower())
            except ValueError:
                return {"status": "error", "message": f"status must be one of: lead, customer, inactive (got {status!r})"}
        try:
            customer = customer_controller.update_customer(db, org_id, UUID(customer_id), CustomerUpdate(**updates))
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        result = {"action": "updated", **_serialize_customer(customer)}
        log("update_customer", {"customer_id": customer_id, **updates}, result)
        return result

    @tool
    def search_customers(query: str = "", status: str = "") -> dict:
        """Search/list customers by name, phone, email, job, pet, or
        interests, optionally filtered by status (lead, customer, inactive).
        Leave both blank to list everyone (first 20)."""
        status_filter = None
        if status.strip():
            try:
                status_filter = CustomerStatus(status.strip().lower())
            except ValueError:
                return {"status": "error", "message": f"status must be one of: lead, customer, inactive (got {status!r})"}
        items, total = customer_controller.list_customers(db, org_id, search=_clean(query), status=status_filter, page=1, page_size=20)
        return {
            "total": total,
            "customers": [
                {"id": str(c.id), "name": c.name, "status": c.status.value, "phone": c.phone, "email": c.email, "interests": c.interests}
                for c in items
            ],
        }

    @tool
    def find_duplicate_customers() -> dict:
        """Find groups of customers that look like duplicates of each other
        (matched by phone, email, or name). Returns which record would be
        kept and which would be merged into it if merge_customers is called."""
        groups = customer_controller.find_duplicate_groups(db, org_id)
        return {
            "groups": [
                {
                    "keep": {"id": str(g[0].id), "name": g[0].name},
                    "duplicates": [{"id": str(c.id), "name": c.name} for c in g[1:]],
                }
                for g in groups
            ]
        }

    @tool
    def add_transaction(customer_id: str, date: str, item: str, amount: float, qty: float = 1, currency: str = "") -> dict:
        """Record a purchase/transaction for a customer. date must be
        YYYY-MM-DD. amount is the unit price (a plain number, no currency
        symbol). currency is an ISO code like NGN, USD, EUR if known."""
        try:
            tx = transaction_controller.add_transaction(
                db, org_id, UUID(customer_id),
                TransactionCreate(date=date, item=item, qty=qty, amount=amount, currency=currency.upper().strip()),
            )
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        from app.schemas.transaction import TransactionOut

        result = {"status": "created", **TransactionOut.model_validate(tx).model_dump(mode="json")}
        log("add_transaction", {"customer_id": customer_id, "date": date, "item": item, "qty": qty, "amount": amount, "currency": currency}, result)
        return result

    @tool
    def update_transaction(customer_id: str, transaction_id: str, date: str = "", item: str = "", amount: float = -1, qty: float = -1, currency: str = "") -> dict:
        """Correct a previously recorded transaction. Only pass the fields
        that should change; leave amount/qty as -1 and others blank to leave
        them unchanged."""
        updates: dict = {}
        if date.strip():
            updates["date"] = date
        if item.strip():
            updates["item"] = item
        if amount >= 0:
            updates["amount"] = amount
        if qty >= 0:
            updates["qty"] = qty
        if currency.strip():
            updates["currency"] = currency.upper().strip()
        try:
            tx = transaction_controller.update_transaction(db, org_id, UUID(customer_id), UUID(transaction_id), TransactionUpdate(**updates))
        except (customer_controller.CustomerNotFoundError, transaction_controller.TransactionNotFoundError):
            return {"status": "error", "message": "No such customer/transaction."}
        from app.schemas.transaction import TransactionOut

        result = {"status": "updated", **TransactionOut.model_validate(tx).model_dump(mode="json")}
        log("update_transaction", {"customer_id": customer_id, "transaction_id": transaction_id, **updates}, result)
        return result

    @tool
    def create_order(customer_id: str, items: str, order_date: str = "", delivery_date: str = "", amount: float = -1, currency: str = "") -> dict:
        """Create an order for a customer - distinct from a transaction, this
        tracks fulfillment (what was ordered, when it's due, whether it's
        been paid/delivered) rather than a completed sale. items is a
        comma-separated list of what was ordered (e.g. "5 bags of rice, 2
        generators"). order_date defaults to today if blank. delivery_date is
        the expected future delivery date (YYYY-MM-DD), leave blank if
        unknown. amount is the order's total value if known (leave as -1 if
        unknown)."""
        import datetime as _dt

        order_items = [OrderItem(name=part.strip()) for part in items.split(",") if part.strip()]
        try:
            order = order_controller.create_order(
                db, org_id, UUID(customer_id),
                OrderCreate(
                    order_date=order_date.strip() or _dt.date.today(),
                    delivery_date=_clean(delivery_date),
                    items=order_items,
                    amount=amount if amount >= 0 else None,
                    currency=_clean(currency.upper() if currency else ""),
                ),
            )
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        from app.schemas.order import OrderOut

        result = {"status": "created", **OrderOut.model_validate(order).model_dump(mode="json")}
        log("create_order", {"customer_id": customer_id, "items": items, "order_date": order_date, "delivery_date": delivery_date, "amount": amount, "currency": currency}, result)
        return result

    @tool
    def set_customer_custom_field(customer_id: str, field_name: str, value: str) -> dict:
        """Set a custom field on a customer. Use this when a new piece of
        information about the customer is a short, clearly-named fact that
        fits a single field (e.g. field_name "Car", value "Toyota Camry"; or
        field_name "Preferred delivery day", value "Saturday"). If you are
        not confident the information cleanly fits as one named field, use
        add_customer_note instead - don't guess at a field name for
        something vague or multi-part."""
        field = field_name.strip()
        if not field:
            return {"status": "error", "message": "field_name is required."}
        try:
            customer = customer_controller.get_customer(db, org_id, UUID(customer_id))
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        updated = customer_controller.update_customer(
            db, org_id, customer.id, CustomerUpdate(extra={**(customer.extra or {}), field: value.strip()})
        )
        result = {"action": "field_set", "field_name": field, "value": value.strip(), **_serialize_customer(updated)}
        log("set_customer_custom_field", {"customer_id": customer_id, "field_name": field, "value": value}, result)
        return result

    @tool
    def add_customer_note(customer_id: str, title: str, content: str) -> dict:
        """Record free-form, ambiguous, or multi-part information about a
        customer as a note rather than a structured field - use this whenever
        the information doesn't cleanly fit a single named field, or you are
        not confident it should be one (e.g. "customer mentioned they're
        moving next month and may pause orders", or anything about a
        customer being a creditor/VIP/special case). The note is flagged for
        a human to review later and will not appear as a customer field
        until someone looks at it - this is the safe default when in doubt,
        prefer it over guessing a field name with set_customer_custom_field."""
        try:
            customer = customer_controller.get_customer(db, org_id, UUID(customer_id))
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        from app.schemas.note import NoteOut

        note = note_controller.create_note(
            db, org_id,
            NoteCreate(title=title.strip() or "Note", content=content.strip(), customer_ids=[customer.id]),
            created_by_agent=True, is_pending_review=True,
        )
        result = {"status": "pending_review", **NoteOut.model_validate(note).model_dump(mode="json")}
        log("add_customer_note", {"customer_id": customer_id, "title": title, "content": content}, result)
        return result

    @tool
    def get_dashboard_summary() -> dict:
        """Get precomputed CRM totals: customer counts by status, sales by
        currency (all-time, this month, last 6 months), top customers, and
        what people have shown interest in. Use this instead of adding up
        customers yourself."""
        from app.controllers import summary_controller

        return summary_controller.get_summary(db, org_id).model_dump(mode="json")

    @tool
    def delete_customer(customer_id: str, reason: str = "") -> dict:
        """Request deletion of a customer record. DESTRUCTIVE and
        irreversible - this does not delete anything immediately. It creates
        a pending confirmation that a human must approve first. Only call
        this when the user has clearly asked to delete/remove a customer."""
        try:
            customer = customer_controller.get_customer(db, org_id, UUID(customer_id))
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        description = f"Delete customer '{customer.name}'." + (f" Reason: {reason}" if reason.strip() else "")
        pending = agent_controller.create_pending_action(db, org_id, user_id, "delete_customer", {"customer_id": customer_id}, description)
        return {"status": "confirm_required", "action_id": str(pending.id), "description": pending.description}

    @tool
    def merge_customers(keep_id: str, merge_id: str) -> dict:
        """Request merging two duplicate customer records into one. DESTRUCTIVE
        and irreversible - this does not merge anything immediately. It
        creates a pending confirmation that a human must approve first.
        keep_id is the record that survives; merge_id is absorbed into it."""
        try:
            keep = customer_controller.get_customer(db, org_id, UUID(keep_id))
            merge = customer_controller.get_customer(db, org_id, UUID(merge_id))
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No such customer(s)."}
        description = f"Merge '{merge.name}' into '{keep.name}' (the duplicate record will be removed)."
        pending = agent_controller.create_pending_action(db, org_id, user_id, "merge_customers", {"keep_id": keep_id, "merge_id": merge_id}, description)
        return {"status": "confirm_required", "action_id": str(pending.id), "description": pending.description}

    return [
        create_customer,
        create_customer_as_new,
        update_customer,
        search_customers,
        find_duplicate_customers,
        add_transaction,
        update_transaction,
        create_order,
        set_customer_custom_field,
        add_customer_note,
        get_dashboard_summary,
        delete_customer,
        merge_customers,
    ]
