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
Destructive tools - EVERY delete or removal, plus merges, sends to real
people, new webhooks and bulk CSV imports - never mutate anything directly:
they create a PendingAction row and return a confirm_required payload. A
human must call the /api/agent/pending/{id}/confirm endpoint before the
action actually runs (executors live in agent_controller).

Read-only tools live in read_tools.py and are included here too; the Ask
Your Data assistant gets only those.
"""
import json
from uuid import UUID

from langchain.tools import tool
from sqlalchemy.orm import Session

from app.agent.read_tools import (
    build_read_tools, find_form, find_segment, find_template, find_webhook, parse_uuid,
)
from app.controllers import (
    agent_controller, customer_controller, form_controller, messaging_controller, note_controller,
    notification_controller, order_controller, segment_controller, settings_controller, transaction_controller,
    webhook_controller,
)
from app.controllers.segment_sql import SegmentSQLError
from app.core.merge_tags import find_placeholders, merge_tag_problems
from app.models.customer import CustomerStatus
from app.schemas.form import FormCreate, FormUpdate
from app.schemas.messaging import EmailTemplateCreate, EmailTemplateUpdate
from app.schemas.segment import SegmentCreate, SegmentFilters, SegmentUpdate
from app.schemas.settings import SettingsUpdate
from app.schemas.webhook import EVENT_TYPES, WebhookSubscriptionCreate, WebhookSubscriptionUpdate
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

    def stage(tool_name: str, payload: dict, description: str) -> dict:
        """Destructive/outward-facing: nothing happens now, a human confirms first."""
        pending = agent_controller.create_pending_action(db, org_id, user_id, tool_name, payload, description)
        return {"status": "confirm_required", "action_id": str(pending.id), "description": pending.description}

    def customer_or_error(customer_id: str):
        cid = parse_uuid(customer_id)
        if not cid:
            return None, {"status": "error", "message": "customer_id must be a customer id - use search_customers to find it."}
        try:
            return customer_controller.get_customer(db, org_id, cid), None
        except customer_controller.CustomerNotFoundError:
            return None, {"status": "error", "message": "No customer with that id."}

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
        """Request deletion of an order. DESTRUCTIVE - nothing is deleted
        now; a human must confirm first. Use when an order was entered in
        error or cancelled and should be removed, not just marked
        undelivered/unpaid (use update_order for status changes)."""
        try:
            order = order_controller._get_order(db, org_id, UUID(customer_id), UUID(order_id))
        except (ValueError, customer_controller.CustomerNotFoundError, order_controller.OrderNotFoundError):
            return {"status": "error", "message": "No such customer/order."}
        items = ", ".join(i.get("name", "?") for i in (order.items or [])) or "no items"
        who = order.customer.name if order.customer else "this customer"
        return stage("delete_order", {"customer_id": customer_id, "order_id": order_id}, f"Delete the order of {items} ({order.order_date}) for {who}.")

    @tool
    def delete_transaction(customer_id: str, transaction_id: str) -> dict:
        """Request deletion of a transaction. DESTRUCTIVE - nothing is
        deleted now; a human must confirm first. Use when the user says a
        transaction was entered in error and should be removed, not just
        corrected (use update_transaction for corrections)."""
        try:
            tx = transaction_controller.get_transaction(db, org_id, UUID(customer_id), UUID(transaction_id))
        except (ValueError, customer_controller.CustomerNotFoundError, transaction_controller.TransactionNotFoundError):
            return {"status": "error", "message": "No such customer/transaction."}
        items = ", ".join(i.get("item", "?") for i in (tx.items or [])) or "no items"
        money = f"{tx.amount:,.2f}" + (f" {tx.currency}" if tx.currency else "")
        return stage("delete_transaction", {"customer_id": customer_id, "transaction_id": transaction_id}, f"Delete the {tx.date} transaction ({items}; {money}).")

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
        """Request deletion of a note. DESTRUCTIVE - nothing is deleted now;
        a human must confirm first. Look up note_id with list_notes first if
        you don't already have it."""
        nid = parse_uuid(note_id)
        try:
            note = note_controller.get_note(db, org_id, nid) if nid else None
        except note_controller.NoteNotFoundError:
            note = None
        if not note:
            return {"status": "error", "message": "No note with that id."}
        return stage("delete_note", {"note_id": note_id}, f"Delete the note '{note.title}'.")

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
        return stage("delete_customer", {"customer_id": customer_id}, description)

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
        return stage("merge_customers", {"keep_id": keep_id, "merge_id": merge_id}, description)

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
            segment = find_segment(db, org_id, segment_name)
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
        return stage("send_customer_email", payload, description)

    # ---------------------------------------------------------- custom fields

    @tool
    def rename_customer_custom_field(customer_id: str, old_name: str, new_name: str) -> dict:
        """Rename one of a customer's custom fields, keeping its value (e.g.
        "Car" -> "Vehicle"). Check list_custom_fields first so you match the
        org's existing spelling."""
        customer, err = customer_or_error(customer_id)
        if err:
            return err
        old, new = old_name.strip(), new_name.strip()
        extra = dict(customer.extra or {})
        if old not in extra:
            return {"status": "error", "message": f"This customer has no custom field {old!r}."}
        if not new or (new in extra and new != old):
            return {"status": "error", "message": "new_name must be non-empty and not already used on this customer."}
        extra = {(new if k == old else k): v for k, v in extra.items()}
        updated = customer_controller.update_customer(db, org_id, customer.id, CustomerUpdate(extra=extra))
        result = {"action": "field_renamed", "old_name": old, "new_name": new, **_serialize_customer(updated)}
        log("rename_customer_custom_field", {"customer_id": customer_id, "old_name": old, "new_name": new}, result)
        return result

    @tool
    def remove_customer_custom_field(customer_id: str, field_name: str) -> dict:
        """Request removal of a custom field (and its value) from one
        customer. DESTRUCTIVE - nothing is removed now; a human must confirm."""
        customer, err = customer_or_error(customer_id)
        if err:
            return err
        field = field_name.strip()
        if field not in (customer.extra or {}):
            return {"status": "error", "message": f"This customer has no custom field {field!r}."}
        return stage("remove_customer_custom_field", {"customer_id": customer_id, "field_name": field},
                     f"Remove the custom field '{field}' ('{customer.extra[field]}') from {customer.name}.")

    @tool
    def import_customers_csv(csv_text: str) -> dict:
        """Request importing customers from CSV text pasted by the user (a
        header row with at least a name column, then one customer per row;
        optional phone, email, item, amount, date, ... columns). People who
        already exist are merged (only blanks are filled in), the rest are
        added. A bulk change, so nothing happens now - a human confirms first."""
        lines = [ln for ln in csv_text.splitlines() if ln.strip()]
        if len(lines) < 2:
            return {"status": "error", "message": "Needs a header row plus at least one data row."}
        return stage("import_customers_csv", {"csv_text": csv_text}, f"Import {len(lines) - 1} row(s) from CSV into the customer list (existing customers are merged, not overwritten).")

    # ---------------------------------------------------------------- segments

    def _filters_from_json(filters_json: str):
        try:
            return SegmentFilters(**json.loads(filters_json)), None
        except Exception as e:  # noqa: BLE001 - reported back so the model can fix its JSON
            return None, {"status": "error", "message": f"filters_json isn't valid ({e.__class__.__name__}) - read get_segment_fields for the format."}

    @tool
    def create_segment(name: str, filters_json: str = "", sql: str = "") -> dict:
        """Save a new customer segment - a named, live group (e.g. "Lapsed
        buyers"). Define it with filters_json (see get_segment_fields for the
        format) OR a SELECT query in sql (see get_segment_sql_schema), not
        both. Check who it matches with preview_segment first. Reversible, so
        it saves immediately."""
        if not name.strip():
            return {"status": "error", "message": "name is required."}
        if find_segment(db, org_id, name) and find_segment(db, org_id, name).name.lower() == name.strip().lower():
            return {"status": "error", "message": f"A segment named {name!r} already exists - use update_segment."}
        if bool(filters_json.strip()) == bool(sql.strip()):
            return {"status": "error", "message": "Pass exactly one of filters_json or sql."}
        filters = SegmentFilters()
        if filters_json.strip():
            filters, err = _filters_from_json(filters_json)
            if err:
                return err
        try:
            segment = segment_controller.create_segment(db, org_id, SegmentCreate(name=name.strip(), filters=filters, sql=sql.strip() or None))
            members = len(segment_controller.resolve_segment(db, segment))
        except SegmentSQLError as e:
            return {"status": "error", "message": f"That query doesn't work: {e}"}
        result = {"status": "created", "id": str(segment.id), "name": segment.name, "members": members}
        log("create_segment", {"name": name, "filters_json": filters_json, "sql": sql}, result)
        return result

    @tool
    def update_segment(segment: str, new_name: str = "", filters_json: str = "", sql: str = "") -> dict:
        """Change a saved segment (by name or id): rename it, or replace its
        filters_json or its sql (pass at most one definition). Read it with
        get_segment first. Reversible, so it saves immediately."""
        found = find_segment(db, org_id, segment)
        if not found:
            return {"status": "error", "message": f"No segment {segment!r} - check list_segments."}
        if filters_json.strip() and sql.strip():
            return {"status": "error", "message": "Pass filters_json or sql, not both."}
        data: dict = {}
        if new_name.strip():
            data["name"] = new_name.strip()
        if filters_json.strip():
            filters, err = _filters_from_json(filters_json)
            if err:
                return err
            data["filters"] = filters
            data["sql"] = ""  # back to visual filters
        if sql.strip():
            data["sql"] = sql.strip()
        if not data:
            return {"status": "error", "message": "Nothing to change - pass new_name, filters_json or sql."}
        try:
            updated = segment_controller.update_segment(db, org_id, found.id, SegmentUpdate(**data))
            members = len(segment_controller.resolve_segment(db, updated))
        except SegmentSQLError as e:
            return {"status": "error", "message": f"That query doesn't work: {e}"}
        result = {"status": "updated", "id": str(updated.id), "name": updated.name, "members": members}
        log("update_segment", {"segment": segment, **{k: (v if isinstance(v, str) else "filters") for k, v in data.items()}}, result)
        return result

    @tool
    def delete_segment(segment: str) -> dict:
        """Request deletion of a saved segment (by name or id). DESTRUCTIVE -
        nothing is deleted now; a human must confirm first."""
        found = find_segment(db, org_id, segment)
        if not found:
            return {"status": "error", "message": f"No segment {segment!r} - check list_segments."}
        return stage("delete_segment", {"segment_id": str(found.id)}, f"Delete the segment '{found.name}'.")

    # --------------------------------------------------------------- templates

    @tool
    def create_email_template(name: str, subject: str, body_html: str) -> dict:
        """Save a reusable email template. body_html may use merge tags (see
        get_merge_tag_guide). It is refused if a merge tag won't work or a
        [placeholder] is left in. Reversible, so it saves immediately."""
        if find_template(db, org_id, name) and find_template(db, org_id, name).name.lower() == name.strip().lower():
            return {"status": "error", "message": f"A template named {name!r} already exists - use update_email_template."}
        problems = merge_tag_problems(db, org_id, subject, body_html)
        if problems:
            return {"status": "error", "message": "Some merge tags won't work - fix them and try again.", "problems": problems}
        placeholders = find_placeholders(subject, body_html)
        if placeholders:
            return {"status": "error", "message": "The template still has placeholders - ask the user what to put there.", "placeholders": placeholders}
        template = messaging_controller.create_template(db, org_id, EmailTemplateCreate(name=name.strip(), subject=subject.strip(), body_html=body_html))
        result = {"status": "created", "id": str(template.id), "name": template.name, "subject": template.subject}
        log("create_email_template", {"name": name, "subject": subject}, result)
        return result

    @tool
    def update_email_template(template: str, new_name: str = "", subject: str = "", body_html: str = "") -> dict:
        """Edit a saved email template (by name or id). Only pass what should
        change. Read it first with get_email_template. Same merge-tag and
        placeholder checks as create_email_template."""
        found = find_template(db, org_id, template)
        if not found:
            return {"status": "error", "message": f"No template {template!r} - check list_email_templates."}
        data = {k: v.strip() if k != "body_html" else v for k, v in {"name": new_name, "subject": subject, "body_html": body_html}.items() if v.strip()}
        if not data:
            return {"status": "error", "message": "Nothing to change."}
        new_subject, new_body = data.get("subject", found.subject), data.get("body_html", found.body_html)
        problems = merge_tag_problems(db, org_id, new_subject, new_body)
        if problems:
            return {"status": "error", "message": "Some merge tags won't work - fix them and try again.", "problems": problems}
        placeholders = find_placeholders(new_subject, new_body)
        if placeholders:
            return {"status": "error", "message": "The template still has placeholders - ask the user what to put there.", "placeholders": placeholders}
        updated = messaging_controller.update_template(db, org_id, found.id, EmailTemplateUpdate(**data))
        result = {"status": "updated", "id": str(updated.id), "name": updated.name, "subject": updated.subject}
        log("update_email_template", {"template": template, **{k: v for k, v in data.items() if k != "body_html"}}, result)
        return result

    @tool
    def delete_email_template(template: str) -> dict:
        """Request deletion of a saved email template (by name or id).
        DESTRUCTIVE - nothing is deleted now; a human must confirm first."""
        found = find_template(db, org_id, template)
        if not found:
            return {"status": "error", "message": f"No template {template!r} - check list_email_templates."}
        return stage("delete_email_template", {"template_id": str(found.id)}, f"Delete the email template '{found.name}'.")

    # ---------------------------------------------------------------- settings

    @tool
    def update_settings(
        biz_name: str = "", industry: str = "", manager_name: str = "", staff_names: str = "", phone: str = "",
        address: str = "", default_currency: str = "", whatsapp_number: str = "", default_country_code: str = "",
        support_email: str = "", qr_message: str = "",
    ) -> dict:
        """Update the business profile in Settings. Only pass the fields that
        should change; blank leaves a field alone. staff_names is a
        comma-separated list that replaces the current staff list.
        default_currency is an ISO code like NGN. whatsapp_number needs the
        country code (e.g. +234 801 234 5678). The sending email address is
        not changeable here - the user does that in the app."""
        raw = {
            "biz_name": biz_name, "industry": industry, "manager_name": manager_name, "phone": phone, "address": address,
            "whatsapp_number": whatsapp_number, "default_country_code": default_country_code,
            "support_email": support_email, "qr_message": qr_message,
        }
        updates: dict = {k: v.strip() for k, v in raw.items() if v.strip()}
        if staff_names.strip():
            updates["staff_names"] = [n.strip() for n in staff_names.split(",") if n.strip()]
        if default_currency.strip():
            code = default_currency.strip().upper()
            if len(code) != 3 or not code.isalpha():
                return {"status": "error", "message": "default_currency must be a 3-letter ISO code like NGN, USD, EUR."}
            updates["default_currency"] = code
        if not updates:
            return {"status": "error", "message": "Nothing to change."}
        try:
            data = SettingsUpdate(**updates)
        except ValueError as e:
            return {"status": "error", "message": str(e).splitlines()[-1] if str(e) else "Invalid settings."}
        settings_controller.update_settings(db, org_id, data)
        result = {"status": "updated", "changed": sorted(updates)}
        log("update_settings", updates, result)
        return result

    # ------------------------------------------------------------------- forms

    @tool
    def create_form(name: str, fields_json: str) -> dict:
        """Create a public intake form. fields_json is a JSON array of
        {"key","label","type","required","category"} where category is
        "customer" (keys: first_name, last_name, phone, email, name, job,
        nationality, pet, address, notes, interests), "transaction" (tx_date,
        tx_item, tx_qty, tx_amount, tx_currency), "order" (order_date,
        order_delivery_date, order_item, order_qty, order_price,
        order_currency) or "custom"; type is text, textarea, tel, email,
        number or date. EVERY form must include the customer fields
        first_name (required), last_name, phone and email."""
        try:
            data = FormCreate(name=name.strip(), fields=json.loads(fields_json))
        except Exception as e:  # noqa: BLE001 - validation text goes back to the model
            return {"status": "error", "message": f"fields_json isn't valid: {str(e).splitlines()[-1] if str(e) else e.__class__.__name__}"}
        form = form_controller.create_form(db, org_id, data)
        result = {"status": "created", "id": str(form.id), "name": form.name, "public_token": form.public_token}
        log("create_form", {"name": name, "fields_json": fields_json}, result)
        return result

    @tool
    def update_form(form: str, new_name: str = "", fields_json: str = "", is_active: str = "") -> dict:
        """Edit a form (by name or id): rename it, replace its whole field
        list (same fields_json format as create_form), or turn it on/off with
        is_active "true"/"false". Only pass what should change. Link tokens
        and signing secrets are not changeable here."""
        found = find_form(db, org_id, form)
        if not found:
            return {"status": "error", "message": f"No form {form!r} - check list_forms."}
        updates: dict = {}
        if new_name.strip():
            updates["name"] = new_name.strip()
        if is_active.strip().lower() in ("true", "false"):
            updates["is_active"] = is_active.strip().lower() == "true"
        try:
            if fields_json.strip():
                updates["fields"] = json.loads(fields_json)
            data = FormUpdate(**updates)
        except Exception as e:  # noqa: BLE001
            return {"status": "error", "message": f"Invalid change: {str(e).splitlines()[-1] if str(e) else e.__class__.__name__}"}
        if not updates:
            return {"status": "error", "message": "Nothing to change."}
        updated = form_controller.update_form(db, org_id, found.id, data)
        result = {"status": "updated", "id": str(updated.id), "name": updated.name, "is_active": updated.is_active}
        log("update_form", {"form": form, **{k: v for k, v in updates.items() if k != "fields"}}, result)
        return result

    @tool
    def delete_form(form: str) -> dict:
        """Request deletion of a form (by name or id). DESTRUCTIVE - its public
        link stops working and nothing is deleted now; a human must confirm."""
        found = find_form(db, org_id, form)
        if not found:
            return {"status": "error", "message": f"No form {form!r} - check list_forms."}
        return stage("delete_form", {"form_id": str(found.id)}, f"Delete the form '{found.name}' (its public link will stop working).")

    # ---------------------------------------------------------------- webhooks

    @tool
    def create_webhook(target_url: str, event_types: str) -> dict:
        """Request a new outgoing webhook: the app will POST the chosen events
        to target_url. event_types is comma-separated from list_webhooks'
        available_events (e.g. "order.created,customer.created"). It sends
        customer data to an outside address, so nothing happens now - a human
        must confirm first."""
        events = [e.strip() for e in event_types.split(",") if e.strip()]
        try:
            WebhookSubscriptionCreate(target_url=target_url.strip(), event_types=events)
        except ValueError as e:
            return {"status": "error", "message": str(e).splitlines()[-1], "available_events": sorted(EVENT_TYPES)}
        return stage("create_webhook", {"target_url": target_url.strip(), "event_types": events},
                     f"Create a webhook sending {', '.join(events)} to {target_url.strip()}.")

    @tool
    def set_webhook_active(webhook: str, active: bool) -> dict:
        """Pause (active=false) or resume (active=true) an existing webhook,
        by id or target URL. Its URL and events are not changed here."""
        found = find_webhook(db, org_id, webhook)
        if not found:
            return {"status": "error", "message": f"No webhook {webhook!r} - check list_webhooks."}
        updated = webhook_controller.update_subscription(db, org_id, found.id, WebhookSubscriptionUpdate(is_active=active))
        result = {"status": "updated", "target_url": updated.target_url, "is_active": updated.is_active}
        log("set_webhook_active", {"webhook": webhook, "active": active}, result)
        return result

    @tool
    def delete_webhook(webhook: str) -> dict:
        """Request deletion of a webhook (by id or target URL). DESTRUCTIVE -
        nothing is deleted now; a human must confirm first."""
        found = find_webhook(db, org_id, webhook)
        if not found:
            return {"status": "error", "message": f"No webhook {webhook!r} - check list_webhooks."}
        return stage("delete_webhook", {"webhook_id": str(found.id)}, f"Delete the webhook to {found.target_url}.")

    # ----------------------------------------------------------- notifications

    @tool
    def mark_notifications_read(notification_id: str = "") -> dict:
        """Mark one notification (by id from list_notifications) as read, or
        all of them when notification_id is blank."""
        if not notification_id.strip():
            count = notification_controller.mark_all_read(db, org_id)
            result = {"status": "updated", "marked_read": count}
        else:
            nid = parse_uuid(notification_id)
            try:
                if not nid:
                    raise notification_controller.NotificationNotFoundError()
                notification_controller.mark_read(db, org_id, nid)
            except notification_controller.NotificationNotFoundError:
                return {"status": "error", "message": "No notification with that id."}
            result = {"status": "updated", "marked_read": 1}
        log("mark_notifications_read", {"notification_id": notification_id}, result)
        return result

    @tool
    def delete_notification(notification_id: str) -> dict:
        """Request deletion of a notification (by id from list_notifications).
        DESTRUCTIVE - nothing is deleted now; a human must confirm first.
        To just clear the unread badge use mark_notifications_read."""
        nid = parse_uuid(notification_id)
        match = next((n for n in notification_controller.list_notifications(db, org_id, limit=100) if n.id == nid), None) if nid else None
        if not match:
            return {"status": "error", "message": "No notification with that id."}
        return stage("delete_notification", {"notification_id": notification_id}, f"Delete the notification '{match.title}'.")


    write_tools = [
        create_customer, create_customer_as_new, update_customer,
        add_transaction, update_transaction, delete_transaction,
        create_order, update_order, delete_order,
        set_customer_custom_field, rename_customer_custom_field, remove_customer_custom_field,
        add_customer_note, create_shared_note, update_note, delete_note,
        delete_customer, merge_customers, import_customers_csv,
        create_segment, update_segment, delete_segment,
        create_email_template, update_email_template, delete_email_template, send_customer_email,
        update_settings,
        create_form, update_form, delete_form,
        create_webhook, set_webhook_active, delete_webhook,
        mark_notifications_read, delete_notification,
    ]
    return build_read_tools(db, org_id) + write_tools
