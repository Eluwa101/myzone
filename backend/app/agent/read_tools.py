"""
The agent's READ-ONLY tools. Shared by both assistants:

- the chat assistant (tools.py adds its write tools on top of these), and
- the Ask Your Data assistant (ask_data.py), which must never change
  anything - so it is handed ONLY what this module builds.

Safety properties, enforced by tests/test_read_tools.py:
- build_read_tools takes no user_id and never calls agent_controller.log_action
  or any create/update/delete controller function - nothing here can write.
- Secrets never leave through a read: webhook signing secrets and form
  signing secrets are reported only as "has a secret", never their value.
- Every list is capped (MAX_LIMIT) so one call can't flood the model's context.
"""
import datetime
import html
import re
from uuid import UUID

from langchain.tools import tool
from sqlalchemy.orm import Session

from app.controllers import (
    activity_controller,
    customer_controller,
    form_controller,
    messaging_controller,
    note_controller,
    notification_controller,
    order_controller,
    segment_controller,
    settings_controller,
    summary_controller,
    webhook_controller,
)
from app.agent.rewrite import RewriteError, build_rewrite_context, rewrite_message as run_rewrite
from app.controllers.merge_tag_suggestions import suggest_for_segment
from app.controllers.segment_fields import FIELD_REGISTRY, OPERATORS_BY_TYPE, list_custom_field_keys
from app.controllers.segment_sql import SegmentSQLError, run_sql_segment, sandbox_schema, schema_as_text
from app.core.merge_tags import MERGE_TAG_GUIDE, TAG_PATTERN, available_merge_tags, merge_tag_problems
from app.models.customer import CustomerStatus
from app.models.outbound_message import MessageChannel, MessageStatus
from app.schemas.customer import CustomerOut
from app.schemas.order import OrderOut
from app.schemas.segment import SegmentFilters
from app.schemas.transaction import TransactionOut
from app.schemas.webhook import EVENT_TYPES

DEFAULT_LIMIT = 25
MAX_LIMIT = 100


def clean(value: str) -> str | None:
    return value.strip() if value and value.strip() else None


def cap(limit: int) -> int:
    return max(1, min(limit if limit > 0 else DEFAULT_LIMIT, MAX_LIMIT))


def parse_date(value: str) -> datetime.date | None:
    try:
        return datetime.date.fromisoformat(value.strip()) if value and value.strip() else None
    except ValueError:
        return None


def text_preview(body: str, length: int = 200) -> str:
    text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body or "", flags=re.IGNORECASE | re.DOTALL)
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return text if len(text) <= length else text[: length - 1].rstrip() + "…"


def find_by_name_or_id(items: list, ident: str, name_attr: str = "name"):
    """A record the user named ("the VIP segment") or whose id the model
    already holds - ids win, names match case-insensitively."""
    wanted = ident.strip().lower()
    if not wanted:
        return None
    for item in items:
        if str(item.id).lower() == wanted:
            return item
    return next((i for i in items if str(getattr(i, name_attr) or "").strip().lower() == wanted), None)


def find_segment(db: Session, org_id: UUID, ident: str):
    return find_by_name_or_id(segment_controller.list_segments(db, org_id), ident)


def find_template(db: Session, org_id: UUID, ident: str):
    return find_by_name_or_id(messaging_controller.list_templates(db, org_id), ident)


def find_form(db: Session, org_id: UUID, ident: str):
    return find_by_name_or_id(form_controller.list_forms(db, org_id), ident)


def find_webhook(db: Session, org_id: UUID, ident: str):
    return find_by_name_or_id(webhook_controller.list_subscriptions(db, org_id), ident, name_attr="target_url")


def parse_uuid(value: str) -> UUID | None:
    try:
        return UUID(value.strip())
    except (ValueError, AttributeError):
        return None


def order_summary(o) -> dict:
    today = datetime.date.today()
    data = OrderOut.model_validate(o).model_dump(mode="json")
    data["overdue"] = bool(o.delivery_date and not o.delivered and o.delivery_date < today)
    return data


def build_read_tools(db: Session, org_id: UUID) -> list:
    # ------------------------------------------------------------------ customers

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
        items, total = customer_controller.list_customers(db, org_id, search=clean(query), status=status_filter, page=1, page_size=20)
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
        by that id rather than by name. Returns the whole record including
        their transactions and orders (with the ids update/delete need)."""
        try:
            customer = customer_controller.get_customer_by_display_id(db, org_id, display_id)
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": f"No customer with id {display_id!r}."}
        # "action" (not "status") - the customer's own lifecycle status is
        # already a field in the spread dict below, and a same-named
        # wrapper key would silently clobber it.
        return {"action": "found", **CustomerOut.model_validate(customer).model_dump(mode="json")}

    @tool
    def get_customer(customer_id: str) -> dict:
        """The full record for one customer by their internal id: every
        field (including birthday, consent date, custom fields and
        unsubscribe state) plus all their transactions and orders with
        their ids - use it to answer detailed questions about a customer or
        to find the transaction_id/order_id an update or delete needs."""
        cid = parse_uuid(customer_id)
        if not cid:
            return {"status": "error", "message": "customer_id must be a customer id - use search_customers to find it."}
        try:
            customer = customer_controller.get_customer(db, org_id, cid)
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        return {"action": "found", **CustomerOut.model_validate(customer).model_dump(mode="json")}

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
    def get_customer_activity(customer_id: str, limit: int = 30) -> dict:
        """A customer's whole history, newest first: emails and WhatsApp chats
        (WhatsApp is logged as "opened" - it can't be confirmed sent), orders,
        purchases, notes, scans, form submissions, profile/status changes,
        merges, and orders or purchases that were edited or deleted. Use it
        to answer "what has happened with this customer?" or "when did we
        last contact them?"."""
        customer, err = None, None
        cid = parse_uuid(customer_id)
        if not cid:
            return {"status": "error", "message": "customer_id must be a customer id - use search_customers to find it."}
        try:
            customer = customer_controller.get_customer(db, org_id, cid)
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        items, total = activity_controller.get_activity(db, org_id, customer, page=1, page_size=cap(limit))
        return {"customer": customer.name, "total": total, "activity": [i.model_dump(mode="json", exclude={"id", "link"}) for i in items]}

    @tool
    def list_custom_fields() -> dict:
        """Every custom field name in use across this org's customers (e.g.
        "Car", "Preferred delivery day") - check it before creating a new
        custom field so you reuse the existing spelling."""
        return {"custom_fields": list_custom_field_keys(db, org_id)}

    # ------------------------------------------------- transactions and orders

    @tool
    def list_transactions(customer_id: str, limit: int = DEFAULT_LIMIT) -> dict:
        """A customer's recorded purchases, newest first, each with its id,
        date, line items, total and currency. Use this to find the
        transaction_id that update_transaction / delete_transaction needs, or
        to answer what a customer has bought."""
        cid = parse_uuid(customer_id)
        if not cid:
            return {"status": "error", "message": "customer_id must be a customer id - use search_customers to find it."}
        try:
            customer = customer_controller.get_customer(db, org_id, cid)
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        txs = sorted(customer.transactions, key=lambda t: t.date, reverse=True)
        return {
            "customer": customer.name,
            "total": len(txs),
            "transactions": [TransactionOut.model_validate(t).model_dump(mode="json") for t in txs[: cap(limit)]],
        }

    @tool
    def list_orders(
        customer_id: str = "", pending_only: bool = False, overdue_only: bool = False, search: str = "", limit: int = DEFAULT_LIMIT
    ) -> dict:
        """List orders, newest first - one customer's (pass customer_id) or
        everyone's. pending_only=true keeps only orders not yet delivered;
        overdue_only=true keeps only undelivered orders whose delivery date
        has passed. search matches item names, notes or the customer's name.
        Each order has its id, items, dates, amount, paid/delivered flags and
        whether it is overdue - the id is what update_order/delete_order need.
        Use this for "what's unpaid / undelivered / due this week" questions."""
        cid = parse_uuid(customer_id) if customer_id.strip() else None
        if customer_id.strip() and not cid:
            return {"status": "error", "message": "customer_id must be a customer id - use search_customers to find it."}
        try:
            orders = (
                order_controller.list_orders(db, org_id, cid)
                if cid
                else order_controller.list_all_orders(db, org_id, pending_only=pending_only, search=clean(search))
            )
        except customer_controller.CustomerNotFoundError:
            return {"status": "error", "message": "No customer with that id."}
        if cid and pending_only:
            orders = [o for o in orders if not o.delivered]
        if cid and clean(search):
            needle = search.strip().lower()
            orders = [o for o in orders if needle in str(o.items).lower() or needle in (o.notes or "").lower()]
        rows = []
        for o in orders:
            row = order_summary(o)
            if overdue_only and not row["overdue"]:
                continue
            row["customer"] = o.customer.name if o.customer else None
            rows.append(row)
        return {"total": len(rows), "orders": rows[: cap(limit)]}

    # -------------------------------------------------------------------- notes

    @tool
    def list_notes(customer_id: str = "", pending_review_only: bool = False, search: str = "") -> dict:
        """List notes, optionally filtered to one customer's notes, to those
        still waiting for human review, or by a search word. Use this to
        find a note's id before calling update_note or delete_note, or to
        answer a question about what's been noted on a customer."""
        cid = parse_uuid(customer_id) if customer_id.strip() else None
        if customer_id.strip() and not cid:
            return {"status": "error", "message": "customer_id must be a customer id - use search_customers to find it."}
        if cid:
            try:
                customer_controller.get_customer(db, org_id, cid)
            except customer_controller.CustomerNotFoundError:
                return {"status": "error", "message": "No customer with that id."}
        notes = note_controller.list_notes(db, org_id, customer_id=cid, pending_only=pending_review_only, search=clean(search))
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

    # -------------------------------------------------------------- analytics

    @tool
    def get_dashboard_summary() -> dict:
        """Get precomputed CRM totals: customer counts by status, sales by
        currency (all-time, this month, last 6 months), top customers, and
        what people have shown interest in. Use this instead of adding up
        customers yourself."""
        return summary_controller.get_summary(db, org_id).model_dump(mode="json")

    @tool
    def get_sales_report(view: str = "monthly", start_date: str = "", end_date: str = "", limit: int = 20) -> dict:
        """Sales over a chosen period, bucketed by currency (amounts in
        different currencies are never added together). view is "monthly"
        (a total per month) or "top_customers" (biggest spenders). Optional
        start_date / end_date are YYYY-MM-DD. For the compact all-time /
        this-month overview use get_dashboard_summary instead."""
        start, end = parse_date(start_date), parse_date(end_date)
        if (start_date.strip() and not start) or (end_date.strip() and not end):
            return {"status": "error", "message": "Dates must be YYYY-MM-DD."}
        if view == "monthly":
            return {"view": view, "months": [m.model_dump(mode="json") for m in summary_controller.get_full_months(db, org_id, start, end)]}
        if view == "top_customers":
            rows = summary_controller.get_full_top_customers(db, org_id, start, end, limit=cap(limit))
            return {"view": view, "top_customers": [r.model_dump(mode="json") for r in rows]}
        return {"status": "error", "message": 'view must be "monthly" or "top_customers".'}

    # ---------------------------------------------------------------- messages

    @tool
    def list_messages(
        customer_id: str = "", status: str = "", channel: str = "", search: str = "", limit: int = DEFAULT_LIMIT
    ) -> dict:
        """The log of messages sent to customers, newest first: who got
        what, when, and whether it was sent, failed or skipped (and why -
        no email, no consent, unsubscribed). Optional filters: customer_id,
        status (sent, failed, skipped, opened - WhatsApp chats opened), channel (email, whatsapp), and a search word
        (matches subject, body or customer name). Use this to answer "did
        that email go out?" or "who did we email last week?"."""
        cid = parse_uuid(customer_id) if customer_id.strip() else None
        if customer_id.strip() and not cid:
            return {"status": "error", "message": "customer_id must be a customer id - use search_customers to find it."}
        try:
            status_filter = MessageStatus(status.strip().lower()) if status.strip() else None
            channel_filter = MessageChannel(channel.strip().lower()) if channel.strip() else None
        except ValueError:
            return {
                "status": "error",
                "message": f"status must be one of: {', '.join(s.value for s in MessageStatus)}; channel one of: {', '.join(c.value for c in MessageChannel)}.",
            }
        q = messaging_controller.query_history(db, org_id, cid, channel_filter, status_filter, clean(search))
        total = q.count()
        return {
            "total": total,
            "messages": [
                {
                    "id": str(m.id),
                    "customer_id": str(m.customer_id),
                    "customer": m.customer.name if m.customer else None,
                    "channel": m.channel.value,
                    "status": m.status.value,
                    "subject": m.subject,
                    "preview": text_preview(m.body, 160),
                    "error": m.error,
                    "sent_at": m.created_at.isoformat() if m.created_at else None,
                }
                for m in q.limit(cap(limit)).all()
            ],
        }

    @tool
    def get_message(message_id: str) -> dict:
        """The full text of one logged message (from list_messages)."""
        mid = parse_uuid(message_id)
        if not mid:
            return {"status": "error", "message": "message_id must come from list_messages."}
        try:
            m = messaging_controller.get_history_message(db, org_id, mid)
        except messaging_controller.OutboundMessageNotFoundError:
            return {"status": "error", "message": "No message with that id."}
        return {
            "id": str(m.id), "customer": m.customer.name if m.customer else None, "channel": m.channel.value,
            "status": m.status.value, "subject": m.subject, "body": text_preview(m.body, 5000), "error": m.error,
            "sent_at": m.created_at.isoformat() if m.created_at else None,
        }

    @tool
    def list_email_templates() -> dict:
        """List this org's saved email templates (name + subject), so you
        can offer to use one by name when sending an email instead of
        writing the content yourself."""
        templates = messaging_controller.list_templates(db, org_id)
        return {"templates": [{"id": str(t.id), "name": t.name, "subject": t.subject} for t in templates]}

    @tool
    def get_email_template(template: str) -> dict:
        """One saved email template in full (subject and HTML body), by name
        or id - use it before editing a template or to show what it says."""
        found = find_template(db, org_id, template)
        if not found:
            return {"status": "error", "message": f"No template {template!r} - check list_email_templates."}
        return {"id": str(found.id), "name": found.name, "subject": found.subject, "body_html": found.body_html}

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
            segment = find_segment(db, org_id, segment_name)
            if not segment:
                return {"status": "error", "message": f"No segment named {segment_name!r} - check list_segments."}
            result["suggested_for_segment"] = suggest_for_segment(db, org_id, segment)
        return result

    @tool
    def preview_email(customer_id: str, subject: str, body_html: str) -> dict:
        """Show exactly how a draft email would read for one customer, with
        merge tags filled in, and flag any tag that won't work or any
        [placeholder] left in. Changes and sends nothing - use it to check a
        draft before send_customer_email."""
        from app.core.merge_tags import find_placeholders, merge_tag_problems

        cid = parse_uuid(customer_id)
        if not cid:
            return {"status": "error", "message": "customer_id must be a customer id - use search_customers to find it."}
        rendered = messaging_controller.preview(db, org_id, cid, subject, body_html)
        if rendered is None:
            return {"status": "error", "message": "No customer with that id."}
        return {
            "subject": rendered[0],
            "body": text_preview(rendered[1], 3000),
            "problems": merge_tag_problems(db, org_id, subject, body_html),
            "placeholders": find_placeholders(subject, body_html),
        }

    @tool
    def rewrite_message(
        text: str, channel: str = "whatsapp", action: str = "shorten", instruction: str = "", keep_merge_tags: bool = True, subject: str = ""
    ) -> dict:
        """Trim, reformat, make friendlier or rewrite a message that is already written, and
        return the new text - it changes and sends nothing. channel is "whatsapp" (plain text)
        or "email" (text is the HTML body; pass the subject too). action is "shorten",
        "reformat", "friendlier" or "rewrite" (rewrite needs an instruction, e.g. "make it more
        formal"). With keep_merge_tags true (the default) every {{merge tag}} comes back exactly
        as written, links and [placeholders] are kept, and if a safe rewrite isn't possible the
        original comes back with a warning. Set keep_merge_tags false only when the user wants
        the tags reworded or removed."""
        business_text, tags_text = build_rewrite_context(db, org_id)
        try:
            result = run_rewrite(
                channel=channel.strip().lower(), action=action.strip().lower(), body=text, subject=clean(subject),
                instruction=clean(instruction), keep_merge_tags=keep_merge_tags, tags_text=tags_text, business_text=business_text,
                check=lambda s, b: merge_tag_problems(db, org_id, s, b),
            )
        except RewriteError as e:
            return {"status": "error", "message": str(e)}
        out = {"text": result["body"], "unchanged": result["unchanged"], "warning": result["warning"]}
        if result["subject"] is not None:
            out["subject"] = result["subject"]
        return out

    # ---------------------------------------------------------------- segments

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
            out.append({"id": str(s.id), "name": s.name, "members": count, "defined_by": "sql" if s.sql else "filters"})
        return {"segments": out}

    @tool
    def get_segment(segment: str) -> dict:
        """One segment's definition (its filter tree, or its SQL) by name or
        id - read it before editing a segment."""
        found = find_segment(db, org_id, segment)
        if not found:
            return {"status": "error", "message": f"No segment {segment!r} - check list_segments."}
        return {"id": str(found.id), "name": found.name, "filters": found.filters, "sql": found.sql}

    @tool
    def list_segment_members(segment: str, limit: int = DEFAULT_LIMIT) -> dict:
        """Who is in a saved segment right now (segments are live, never a
        stale snapshot), by segment name or id."""
        found = find_segment(db, org_id, segment)
        if not found:
            return {"status": "error", "message": f"No segment {segment!r} - check list_segments."}
        try:
            members = segment_controller.resolve_segment(db, found)
        except SegmentSQLError as e:
            return {"status": "error", "message": f"That segment's SQL doesn't run: {e}"}
        return {
            "segment": found.name,
            "total": len(members),
            "members": [
                {"id": str(c.id), "name": c.name, "email": c.email, "phone": c.phone, "status": c.status.value}
                for c in members[: cap(limit)]
            ],
        }

    @tool
    def get_segment_fields() -> dict:
        """What a segment filter can test: every field with its type, the
        operators allowed for each type, and this org's custom fields (use
        them as "extra.<name>"). Read it before writing filters_json for
        create_segment / update_segment / preview_segment."""
        return {
            "fields": [{"key": f.key, "label": f.label, "type": f.type, "choices": f.choices} for f in FIELD_REGISTRY.values()],
            "operators_by_type": OPERATORS_BY_TYPE,
            "custom_fields": [f"extra.{k}" for k in list_custom_field_keys(db, org_id)],
            "filters_format": (
                'A group: {"type":"group","combinator":"and"|"or"|"nor","conditions":[...]} whose conditions are '
                'leaves {"type":"condition","field":"status","operator":"equals","value":"lead"} or nested groups. '
                '"between" also takes value2; "in_list"/"not_in_list" take values:[...]; '
                '"within_last_days"/"over_days_ago" take a day count as value.'
            ),
        }

    @tool
    def get_segment_sql_schema() -> dict:
        """The read-only tables and columns a custom-SQL segment can query.
        A segment's SQL must be a single SELECT returning customer ids."""
        return {"schema": schema_as_text(sandbox_schema(db, org_id))}

    @tool
    def preview_segment(filters_json: str = "", sql: str = "", limit: int = DEFAULT_LIMIT) -> dict:
        """Who a filter tree (filters_json) or a SELECT query (sql) would
        match, WITHOUT saving anything - use it to check a segment before
        create_segment. Pass one of the two."""
        import json

        if bool(filters_json.strip()) == bool(sql.strip()):
            return {"status": "error", "message": "Pass exactly one of filters_json or sql."}
        try:
            if sql.strip():
                members = run_sql_segment(db, org_id, sql)
            else:
                members = segment_controller.resolve_members(db, org_id, SegmentFilters(**json.loads(filters_json)))
        except SegmentSQLError as e:
            return {"status": "error", "message": f"That query doesn't run: {e}"}
        except Exception as e:  # noqa: BLE001 - bad JSON / bad filter shape reported back so the model can fix it
            return {"status": "error", "message": f"Those filters aren't valid ({e.__class__.__name__}) - check get_segment_fields."}
        return {
            "total": len(members),
            "members": [{"id": str(c.id), "name": c.name, "status": c.status.value} for c in members[: cap(limit)]],
        }

    # --------------------------------------------------------- settings, forms

    @tool
    def get_settings() -> dict:
        """The business profile and preferences from Settings: business
        name, industry, manager, staff, phone, address, default currency,
        WhatsApp number, default country code and the support email."""
        s = settings_controller.get_settings(db, org_id)
        return {
            "biz_name": s.biz_name, "industry": s.industry, "team_size": s.team_size, "manager_name": s.manager_name,
            "staff_names": s.staff_names or [], "phone": s.phone, "address": s.address,
            "default_currency": s.default_currency, "whatsapp_number": s.whatsapp_number,
            "default_country_code": s.default_country_code, "support_email": s.support_email,
            "qr_message": s.qr_message, "brand_color": s.brand_color,
        }

    @tool
    def list_forms() -> dict:
        """The org's public intake forms: name, active or not, its fields, the
        token in its public link, and how many submissions it has had."""
        out = []
        for f in form_controller.list_forms(db, org_id):
            out.append({
                "id": str(f.id), "name": f.name, "is_active": f.is_active, "public_token": f.public_token,
                "signing_enabled": bool(f.webhook_secret),  # never the secret itself
                "fields": f.fields, "submissions": form_controller.query_submissions(db, org_id, f.id).count(),
            })
        return {"forms": out}

    @tool
    def list_form_submissions(form: str, limit: int = DEFAULT_LIMIT) -> dict:
        """What people submitted through one form (by form name or id),
        newest first, and which customer record each created or matched."""
        found = find_form(db, org_id, form)
        if not found:
            return {"status": "error", "message": f"No form {form!r} - check list_forms."}
        q = form_controller.query_submissions(db, org_id, found.id)
        return {
            "form": found.name,
            "total": q.count(),
            "submissions": [
                {
                    "id": str(s.id), "customer_id": str(s.customer_id) if s.customer_id else None,
                    "customer": s.customer_name, "answers": s.raw_payload, "submitted_at": s.created_at.isoformat(),
                }
                for s in q.limit(cap(limit)).all()
            ],
        }

    # ---------------------------------------------------- scans, notifications

    @tool
    def list_scans(limit: int = 20) -> dict:
        """Recently scanned documents (receipts, forms, handwritten notes):
        their status (processing, done, needs_review, failed), what was read
        from them and what was done with it."""
        from app.controllers import scan_controller

        return {
            "scans": [
                {
                    "id": str(s.id), "status": s.status, "document_type": s.document_type, "summary": s.summary,
                    "customer_id": str(s.customer_id) if s.customer_id else None, "display_id": s.display_id,
                    "actions": s.actions or [], "error": s.error, "scanned_at": s.created_at.isoformat(),
                }
                for s in scan_controller.list_scans(db, org_id, limit=cap(limit))
            ]
        }

    @tool
    def list_notifications(unread_only: bool = False, limit: int = 20) -> dict:
        """The org's in-app notifications (new orders, failed emails, notes
        needing review, ...), newest first."""
        items = notification_controller.list_notifications(db, org_id, limit=100)
        if unread_only:
            items = [n for n in items if not n.read]
        return {
            "unread": notification_controller.unread_count(db, org_id),
            "notifications": [
                {"id": str(n.id), "type": n.type, "title": n.title, "body": n.body, "read": n.read, "at": n.created_at.isoformat()}
                for n in items[: cap(limit)]
            ],
        }

    # --------------------------------------------------------------- webhooks

    @tool
    def list_webhooks() -> dict:
        """The org's outgoing webhook subscriptions: target URL, which
        events trigger it and whether it is active. Signing secrets are
        never shown."""
        return {
            "available_events": sorted(EVENT_TYPES),
            "webhooks": [
                {"id": str(w.id), "target_url": w.target_url, "event_types": w.event_types, "is_active": w.is_active}
                for w in webhook_controller.list_subscriptions(db, org_id)
            ],
        }

    @tool
    def list_webhook_deliveries(webhook: str, limit: int = 10) -> dict:
        """Recent delivery attempts for one webhook (by id or target URL):
        event, outcome and response code - use it to diagnose a webhook that
        isn't arriving."""
        found = find_webhook(db, org_id, webhook)
        if not found:
            return {"status": "error", "message": f"No webhook {webhook!r} - check list_webhooks."}
        deliveries = webhook_controller.list_deliveries(db, org_id, found.id)
        return {
            "webhook": found.target_url,
            "deliveries": [
                {"event_type": d.event_type, "status": d.status, "response_code": d.response_code, "attempts": d.attempt_count, "at": d.created_at.isoformat()}
                for d in deliveries[: cap(limit)]
            ],
        }

    return [
        search_customers, find_customer_by_id, get_customer, get_customer_activity, find_duplicate_customers, list_custom_fields,
        list_transactions, list_orders, list_notes,
        get_dashboard_summary, get_sales_report,
        list_messages, get_message, list_email_templates, get_email_template, get_merge_tag_guide, preview_email, rewrite_message,
        list_segments, get_segment, list_segment_members, get_segment_fields, get_segment_sql_schema, preview_segment,
        get_settings, list_forms, list_form_submissions, list_scans, list_notifications,
        list_webhooks, list_webhook_deliveries,
    ]
