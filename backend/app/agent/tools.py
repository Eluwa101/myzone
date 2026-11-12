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
import json
from uuid import UUID

from langchain.tools import tool
from sqlalchemy.orm import Session

from app.controllers import agent_controller, customer_controller, messaging_controller, note_controller, order_controller, segment_controller, settings_controller, transaction_controller
from app.controllers.merge_tag_suggestions import suggest_for_segment
from app.controllers.segment_sql import SegmentSQLError
from app.core.merge_tags import MERGE_TAG_GUIDE, TAG_PATTERN, available_merge_tags, find_placeholders, merge_tag_problems
from app.models.customer import CustomerStatus
from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.schemas.note import NoteCreate, NoteUpdate
from app.schemas.order import OrderCreate, OrderItem, OrderUpdate
from app.schemas.transaction import TransactionCreate, TransactionItem, TransactionUpdate


def _clean(value: str) -> str | None:
    return value.strip() if value and value.strip() else None


def _serialize_customer(customer) -> dict:
    from app.schemas.customer import CustomerOut

    return CustomerOut.model_validate(customer).model_dump(mode="json")


def build_tools(db: Session, org_id: UUID, user_id: UUID) -> list:
    def log(tool_name: str, payload: dict, result: dict) -> None:
        agent_controller.log_action(db, org_id, user_id, tool_name, payload, result)

    def default_currency() -> str:
        return (settings_controller.get_settings(db, org_id).default_currency or "").upper()

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
        first_name, last_name = customer_controller.split_name(name)
        data = CustomerCreate(
            first_name=first_name, last_name=last_name, phone=_clean(phone), email=_clean(email), job=_clean(job),
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
        first_name, last_name = customer_controller.split_name(name)
        data = CustomerCreate(
            first_name=first_name, last_name=last_name, phone=_clean(phone), email=_clean(email), job=_clean(job),
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
            "phone": _clean(phone), "email": _clean(email), "job": _clean(job),
            "nationality": _clean(nationality), "pet": _clean(pet), "address": _clean(address),
            "notes": _clean(notes), "interests": _clean(interests),
        }
        updates = {k: v for k, v in fields.items() if v is not None}
        if name.strip():
            first_name, last_name = customer_controller.split_name(name)
            updates["first_name"] = first_name
            updates["last_name"] = last_name
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
        """Search/list customers by name, phone, email, job, pet,
        interests, their CR-id (e.g. "CR007"), or an item name from any of
        their past transactions (e.g. "rice" finds everyone who bought
        rice) - optionally filtered by status (lead, customer, inactive).
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
                {
                    "id": str(c.id),
                    "display_id": c.display_id,
                    "name": c.name,
                    "status": c.status.value,
                    "phone": c.phone,
                    "email": c.email,
                    "interests": c.interests,
                }
                for c in items
            ],
        }

    @tool
    def find_customer_by_id(display_id: str) -> dict:
        """Look up the one customer with this exact CR-id (e.g. "CR007" -
        the short id shown on their profile, often written by hand on a
        receipt or document). Use this whenever a customer is referenced
        by that id rather than by name."""
        try:
            customer = customer_controller.get_customer_by_display_id(db, org_id, display_id)
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": f"No customer with id {display_id!r}."}
        # "action" (not "status") - the customer's own lifecycle status is
        # already a field in the spread dict below, and a same-named
        # wrapper key would silently clobber it.
        return {"action": "found", **_serialize_customer(customer)}

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
    def add_transaction(
        customer_id: str,
        date: str,
        item: str = "",
        amount: float = -1,
        qty: float = 1,
        currency: str = "",
        items_json: str = "",
    ) -> dict:
        """Record a purchase/transaction for a customer. date must be
        YYYY-MM-DD. For a single item bought, pass item and amount (this
        item's own total price, not a per-unit price - e.g. 2 bags of rice
        sold together for 5000 is item="Rice", qty=2, amount=5000). For
        several items bought together in the SAME checkout, leave item/amount
        blank and pass items_json instead: a JSON array like
        '[{"item": "Rice", "qty": 2, "amount": 5000}, {"item": "Sugar", "qty": 1, "amount": 1200}]'
        - do NOT call add_transaction once per item for one purchase, that
        would wrongly record them as separate transactions. currency is an
        ISO code like NGN, USD, EUR; if left blank, the organization's
        configured default currency is used."""
        if items_json.strip():
            try:
                raw_items = json.loads(items_json)
                line_items = [TransactionItem(item=i["item"], qty=i.get("qty", 1), amount=i["amount"]) for i in raw_items]
            except (ValueError, KeyError, TypeError, AttributeError):
                return {"status": "error", "message": 'items_json must be a JSON array of {"item", "qty", "amount"} objects.'}
        elif item.strip() and amount >= 0:
            line_items = [TransactionItem(item=item, qty=qty, amount=amount)]
        else:
            return {"status": "error", "message": "Provide either item + amount for a single item, or items_json for several."}
        resolved_currency = currency.upper().strip() or default_currency()
        try:
            tx = transaction_controller.add_transaction(
                db, org_id, UUID(customer_id),
                TransactionCreate(date=date, items=line_items, currency=resolved_currency),
            )
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        from app.schemas.transaction import TransactionOut

        result = {"status": "created", **TransactionOut.model_validate(tx).model_dump(mode="json")}
        log("add_transaction", {"customer_id": customer_id, "date": date, "items": [i.model_dump() for i in line_items], "currency": resolved_currency}, result)
        return result

    @tool
    def update_transaction(
        customer_id: str,
        transaction_id: str,
        date: str = "",
        item: str = "",
        amount: float = -1,
        qty: float = -1,
        currency: str = "",
        items_json: str = "",
    ) -> dict:
        """Correct a previously recorded transaction. For a transaction with
        several items, pass items_json (same JSON-array format as
        add_transaction) to replace its whole item list. For a single-item
        transaction, item/amount/qty edit that one line - leave them blank/-1
        to leave unchanged. Leave currency blank to leave it unchanged."""
        updates: dict = {}
        if date.strip():
            updates["date"] = date
        if currency.strip():
            updates["currency"] = currency.upper().strip()
        if items_json.strip():
            try:
                raw_items = json.loads(items_json)
                updates["items"] = [TransactionItem(item=i["item"], qty=i.get("qty", 1), amount=i["amount"]) for i in raw_items]
            except (ValueError, KeyError, TypeError, AttributeError):
                return {"status": "error", "message": 'items_json must be a JSON array of {"item", "qty", "amount"} objects.'}
        elif item.strip() or amount >= 0 or qty >= 0:
            try:
                current = transaction_controller.get_transaction(db, org_id, UUID(customer_id), UUID(transaction_id))
            except (customer_controller.CustomerNotFoundError, transaction_controller.TransactionNotFoundError):
                return {"status": "error", "message": "No such customer/transaction."}
            if len(current.items or []) != 1:
                return {"status": "error", "message": "This transaction has multiple items - use items_json to replace the whole list instead."}
            line = dict(current.items[0])
            if item.strip():
                line["item"] = item.strip()
            if amount >= 0:
                line["amount"] = amount
            if qty >= 0:
                line["qty"] = qty
            updates["items"] = [TransactionItem(**line)]
        try:
            tx = transaction_controller.update_transaction(db, org_id, UUID(customer_id), UUID(transaction_id), TransactionUpdate(**updates))
        except (customer_controller.CustomerNotFoundError, transaction_controller.TransactionNotFoundError):
            return {"status": "error", "message": "No such customer/transaction."}
        from app.schemas.transaction import TransactionOut

        result = {"status": "updated", **TransactionOut.model_validate(tx).model_dump(mode="json")}
        loggable_updates = {k: ([i.model_dump() for i in v] if k == "items" else v) for k, v in updates.items()}
        log("update_transaction", {"customer_id": customer_id, "transaction_id": transaction_id, **loggable_updates}, result)
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
        unknown). currency is an ISO code like NGN, USD, EUR; if left blank
        and amount is known, the organization's configured default currency
        is used."""
        import datetime as _dt

        order_items = [OrderItem(name=part.strip()) for part in items.split(",") if part.strip()]
        resolved_currency = _clean(currency.upper()) if currency.strip() else (default_currency() or None if amount >= 0 else None)
        try:
            order = order_controller.create_order(
                db, org_id, UUID(customer_id),
                OrderCreate(
                    order_date=order_date.strip() or _dt.date.today(),
                    delivery_date=_clean(delivery_date),
                    items=order_items,
                    amount=amount if amount >= 0 else None,
                    currency=resolved_currency,
                ),
            )
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        from app.schemas.order import OrderOut

        result = {"status": "created", **OrderOut.model_validate(order).model_dump(mode="json")}
        log("create_order", {"customer_id": customer_id, "items": items, "order_date": order_date, "delivery_date": delivery_date, "amount": amount, "currency": currency}, result)
        return result

    @tool
    def update_order(
        customer_id: str,
        order_id: str,
        order_date: str = "",
        delivery_date: str = "",
        items: str = "",
        amount: float = -1,
        currency: str = "",
        paid: str = "",
        delivered: str = "",
    ) -> dict:
        """Update an existing order - e.g. set or change its delivery date,
        mark it paid or delivered, or correct its items/amount. Only pass
        the fields that should change; leave the rest blank/-1. items, if
        given, replaces the whole item list as a comma-separated list (e.g.
        "5 bags of rice, 2 generators"). paid/delivered must be "true" or
        "false" if given."""
        updates: dict = {}
        if order_date.strip():
            updates["order_date"] = order_date.strip()
        if delivery_date.strip():
            updates["delivery_date"] = delivery_date.strip()
        if items.strip():
            updates["items"] = [OrderItem(name=part.strip()) for part in items.split(",") if part.strip()]
        if amount >= 0:
            updates["amount"] = amount
        if currency.strip():
            updates["currency"] = currency.upper().strip()
        if paid.strip():
            updates["paid"] = paid.strip().lower() == "true"
        if delivered.strip():
            updates["delivered"] = delivered.strip().lower() == "true"
        try:
            order = order_controller.update_order(db, org_id, UUID(customer_id), UUID(order_id), OrderUpdate(**updates))
        except (customer_controller.CustomerNotFoundError, order_controller.OrderNotFoundError):
            return {"status": "error", "message": "No such customer/order."}
        from app.schemas.order import OrderOut

        result = {"status": "updated", **OrderOut.model_validate(order).model_dump(mode="json")}
        log("update_order", {"customer_id": customer_id, "order_id": order_id, **{k: v for k, v in updates.items() if k != "items"}}, result)
        return result

    @tool
    def delete_order(customer_id: str, order_id: str) -> dict:
        """Delete an order record entirely - use when an order was entered
        in error or was cancelled and should be removed, not just marked
        undelivered/unpaid (use update_order for status changes)."""
        try:
            order_controller.delete_order(db, org_id, UUID(customer_id), UUID(order_id))
        except (customer_controller.CustomerNotFoundError, order_controller.OrderNotFoundError):
            return {"status": "error", "message": "No such customer/order."}
        result = {"status": "deleted", "order_id": order_id}
        log("delete_order", {"customer_id": customer_id, "order_id": order_id}, result)
        return result

    @tool
    def delete_transaction(customer_id: str, transaction_id: str) -> dict:
        """Delete a transaction record entirely - use when the user says a
        transaction was entered in error and should be removed, not just
        corrected (use update_transaction for corrections)."""
        try:
            transaction_controller.delete_transaction(db, org_id, UUID(customer_id), UUID(transaction_id))
        except (customer_controller.CustomerNotFoundError, transaction_controller.TransactionNotFoundError):
            return {"status": "error", "message": "No such customer/transaction."}
        result = {"status": "deleted", "transaction_id": transaction_id}
        log("delete_transaction", {"customer_id": customer_id, "transaction_id": transaction_id}, result)
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
    def create_shared_note(customer_ids: str, title: str, content: str) -> dict:
        """Create a note and attach it to one or more specific customers,
        when the user directly instructs you to add/save a note (e.g. "add
        a note on Ada and Bola that they're both creditors who still owe for
        last month"). customer_ids is a comma-separated list of customer
        ids - look them up first with search_customers if you only have
        names. Use this (not add_customer_note) whenever the user explicitly
        asked for a note to be created; it does not need human review since
        the user instructed it directly."""
        ids = [cid.strip() for cid in customer_ids.split(",") if cid.strip()]
        if not ids:
            return {"status": "error", "message": "customer_ids is required - look up the customer(s) with search_customers first."}
        try:
            parsed_ids = [UUID(cid) for cid in ids]
        except ValueError:
            return {"status": "error", "message": "customer_ids must be valid customer ids, not names - use search_customers first."}
        from app.schemas.note import NoteOut

        note = note_controller.create_note(
            db, org_id,
            NoteCreate(title=title.strip() or "Note", content=content.strip(), customer_ids=parsed_ids),
            created_by_agent=True, is_pending_review=False,
        )
        result = {"status": "created", **NoteOut.model_validate(note).model_dump(mode="json")}
        log("create_shared_note", {"customer_ids": customer_ids, "title": title, "content": content}, result)
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
    def list_notes(customer_id: str = "") -> dict:
        """List notes, optionally filtered to one customer's notes. Use this
        to find a note's id before calling update_note or delete_note, or to
        answer a question about what's been noted on a customer."""
        cid = UUID(customer_id) if customer_id.strip() else None
        if cid:
            try:
                customer_controller.get_customer(db, org_id, cid)
            except customer_controller.CustomerNotFoundError:
                return {"status": "error", "message": "No customer with that id."}
        notes = note_controller.list_notes(db, org_id, customer_id=cid)
        return {
            "notes": [
                {
                    "id": str(n.id), "title": n.title, "content": n.content,
                    "pending_review": n.is_pending_review,
                    "customers": [c.name for c in n.customers],
                }
                for n in notes
            ]
        }

    @tool
    def update_note(note_id: str, title: str = "", content: str = "", mark_reviewed: str = "") -> dict:
        """Correct an existing note's title or content, or mark it reviewed.
        Only pass the fields that should change. mark_reviewed must be
        "true" or "false" if given - set it to "true" once a pending note
        has been looked at (the same effect as a human tapping "Mark
        reviewed"). Look up note_id with list_notes first if you don't
        already have it."""
        updates: dict = {}
        if title.strip():
            updates["title"] = title.strip()
        if content.strip():
            updates["content"] = content.strip()
        if mark_reviewed.strip():
            updates["is_pending_review"] = mark_reviewed.strip().lower() != "true"
        try:
            note = note_controller.update_note(db, org_id, UUID(note_id), NoteUpdate(**updates))
        except note_controller.NoteNotFoundError:
            return {"status": "error", "message": "No note with that id."}
        from app.schemas.note import NoteOut

        result = {"status": "updated", **NoteOut.model_validate(note).model_dump(mode="json")}
        log("update_note", {"note_id": note_id, **updates}, result)
        return result

    @tool
    def delete_note(note_id: str) -> dict:
        """Delete a note entirely - use when the user says a note was added
        in error or is no longer relevant. Look up note_id with list_notes
        first if you don't already have it."""
        try:
            note_controller.delete_note(db, org_id, UUID(note_id))
        except note_controller.NoteNotFoundError:
            return {"status": "error", "message": "No note with that id."}
        result = {"status": "deleted", "note_id": note_id}
        log("delete_note", {"note_id": note_id}, result)
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

    @tool
    def list_email_templates() -> dict:
        """List this org's saved email templates (name + subject), so you
        can offer to use one by name when sending an email instead of
        writing the content yourself."""
        templates = messaging_controller.list_templates(db, org_id)
        return {"templates": [{"id": str(t.id), "name": t.name, "subject": t.subject} for t in templates]}

    def _find_segment(name: str):
        wanted = name.strip().lower()
        return next((s for s in segment_controller.list_segments(db, org_id) if s.name.strip().lower() == wanted), None)

    @tool
    def list_segments() -> dict:
        """List this org's saved customer segments (name, member count, and
        whether it's defined by filters or custom SQL) - use a segment's name
        with send_customer_email to email everyone in it."""
        out = []
        for s in segment_controller.list_segments(db, org_id):
            try:
                count = len(segment_controller.resolve_segment(db, s))
            except SegmentSQLError:
                count = None
            out.append({"name": s.name, "members": count, "defined_by": "sql" if s.sql else "filters"})
        return {"segments": out}

    @tool
    def get_merge_tag_guide(segment_name: str = "") -> dict:
        """How merge tags work - single values, {{#each}} lists of a
        customer's purchases/orders with filters, {{#if}} conditions,
        totals like {{count ...}} / {{sum ...}} - plus every single-value
        tag this org has. Call this before writing an email body that needs
        anything beyond a plain greeting. Pass segment_name to also get the
        tags that fit that segment particularly well."""
        result: dict = {
            "guide": MERGE_TAG_GUIDE,
            "tags": [t["tag"] for t in available_merge_tags(db, org_id) if TAG_PATTERN.fullmatch(t["tag"])],
        }
        if segment_name.strip():
            segment = _find_segment(segment_name)
            if not segment:
                return {"status": "error", "message": f"No segment named {segment_name!r} - check list_segments."}
            result["suggested_for_segment"] = suggest_for_segment(db, org_id, segment)
        return result

    @tool
    def send_customer_email(
        customer_ids: str = "", template_name: str = "", subject: str = "", body_html: str = "", segment_name: str = ""
    ) -> dict:
        """Request sending an email to one or more customers. Reaches real
        people, so this never sends immediately - it creates a pending
        confirmation a human must approve first (same pattern as
        delete_customer/merge_customers).
        Recipients: either customer_ids (comma-separated customer ids - look
        them up with search_customers or find_customer_by_id first, not
        names) or segment_name (a saved segment - see list_segments; everyone
        in it right now).
        Content: either template_name (an existing saved template - check
        list_email_templates first) or your own subject and body_html (HTML).
        body_html can use merge tags filled in per recipient - call
        get_merge_tag_guide first for anything beyond {{customer.first_name}}
        / {{business.name}}. Never invent prices, discounts or links: ask the
        user. The request is refused if a merge tag won't work or a
        [placeholder] is left in - fix it (or ask the user for the value)
        and call again."""
        if segment_name.strip() and customer_ids.strip():
            return {"status": "error", "message": "Pass either customer_ids or segment_name, not both."}
        segment = None
        if segment_name.strip():
            segment = _find_segment(segment_name)
            if not segment:
                return {"status": "error", "message": f"No segment named {segment_name!r} - check list_segments."}
            try:
                parsed_ids = [str(c.id) for c in segment_controller.resolve_segment(db, segment)]
            except SegmentSQLError as e:
                return {"status": "error", "message": f"That segment's SQL doesn't run: {e}"}
            if not parsed_ids:
                return {"status": "error", "message": f"The segment {segment.name!r} has no members right now."}
        else:
            ids = [cid.strip() for cid in customer_ids.split(",") if cid.strip()]
            if not ids:
                return {"status": "error", "message": "customer_ids or segment_name is required - look up the customer(s) first."}
            try:
                parsed_ids = [str(UUID(cid)) for cid in ids]
            except ValueError:
                return {"status": "error", "message": "customer_ids must be valid customer ids, not names - look them up first."}

        template_id = None
        resolved_subject, resolved_body = subject.strip(), body_html.strip()
        if template_name.strip():
            match = next(
                (t for t in messaging_controller.list_templates(db, org_id) if t.name.lower() == template_name.strip().lower()),
                None,
            )
            if not match:
                return {"status": "error", "message": f"No saved template named {template_name!r} - check list_email_templates."}
            template_id = str(match.id)
            resolved_subject = resolved_subject or match.subject
            resolved_body = resolved_body or match.body_html

        if not resolved_subject or not resolved_body:
            return {"status": "error", "message": "Provide subject and body_html, or a template_name to use."}

        problems = merge_tag_problems(db, org_id, resolved_subject, resolved_body)
        if problems:
            return {"status": "error", "message": "Some merge tags won't work - fix them and try again.", "problems": problems}
        placeholders = find_placeholders(resolved_subject, resolved_body)
        if placeholders:
            return {
                "status": "error",
                "message": "The email still has placeholders - ask the user what to put there, then try again.",
                "placeholders": placeholders,
            }

        audience = f"everyone in segment '{segment.name}' ({len(parsed_ids)} customer(s))" if segment else f"{len(parsed_ids)} customer(s)"
        description = f"Send email to {audience}: {resolved_subject}"
        payload = {"customer_ids": parsed_ids, "subject": resolved_subject, "body_html": resolved_body, "template_id": template_id}
        pending = agent_controller.create_pending_action(db, org_id, user_id, "send_customer_email", payload, description)
        return {"status": "confirm_required", "action_id": str(pending.id), "description": pending.description}

    return [
        create_customer,
        create_customer_as_new,
        update_customer,
        search_customers,
        find_customer_by_id,
        find_duplicate_customers,
        add_transaction,
        update_transaction,
        delete_transaction,
        create_order,
        update_order,
        delete_order,
        set_customer_custom_field,
        add_customer_note,
        create_shared_note,
        list_notes,
        update_note,
        delete_note,
        get_dashboard_summary,
        delete_customer,
        merge_customers,
        list_email_templates,
        list_segments,
        get_merge_tag_guide,
        send_customer_email,
    ]
