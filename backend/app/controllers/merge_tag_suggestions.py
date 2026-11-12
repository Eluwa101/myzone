"""Merge tags worth using when emailing one particular segment - worked
out from what the segment actually selects on, with no AI involved.

A visual-builder segment is read condition by condition ("last purchase
over 60 days ago" -> days since last purchase, latest items). A SQL
segment is parsed with sqlglot: words it searches item names for become
ready-made purchase lists / counts / totals for that item, `date('now',
'-N days')` windows become "in the last N days" lists, and so on.

Every suggestion is an exact tag/snippet the resolver understands, and
each carries a short reason so the user can see why it was suggested."""
import re
from uuid import UUID

import sqlglot
from sqlglot import exp
from sqlalchemy.orm import Session

from app.controllers.segment_fields import list_custom_field_keys
from app.controllers.segment_sql import _custom_field_columns
from app.core.merge_tags import _slugify
from app.models.segment import Segment

MAX_SUGGESTIONS = 16

_ROW = "{{date}} - {{items}} - {{currency}} {{amount}}"


class _Suggestions:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, label: str, tag: str, reason: str) -> None:
        if all(s["tag"] != tag for s in self.items):
            self.items.append({"label": label, "tag": tag, "reason": reason})

    # --- reusable bundles ---

    def purchases(self, reason: str) -> None:
        self.add("Last 3 purchases", "{{#each transactions limit 3}}\n" + _ROW + "\n{{/each}}", reason)
        self.add("Days since last purchase", "{{stats.days_since_last_purchase}}", reason)
        self.add("Lifetime spend", "{{stats.lifetime_spend}}", reason)

    def item(self, word: str, orders: bool = False) -> None:
        reason = f'Your segment looks for "{word}"'
        if orders:
            self.add(
                f'Orders with "{word}"',
                f'{{{{#each orders where item contains "{word}"}}}}\n{{{{date}}}} - {{{{items}}}} - delivered: {{{{delivered}}}}\n{{{{/each}}}}',
                reason,
            )
            self.add(f'Times they ordered "{word}"', f'{{{{count orders where item contains "{word}"}}}}', reason)
            return
        self.add(
            f'Purchases with "{word}"',
            f'{{{{#each transactions where item contains "{word}"}}}}\n' + _ROW + "\n{{/each}}",
            reason,
        )
        self.add(f'Times they bought "{word}"', f'{{{{count transactions where item contains "{word}"}}}}', reason)
        self.add(f'Spent on "{word}"', f'{{{{sum transaction_items.amount where item contains "{word}"}}}}', reason)
        self.add(
            f'If they bought "{word}" 3+ times',
            f'{{{{#if (count transactions where item contains "{word}") >= 3}}}}\nThank you for being a regular!\n{{{{/if}}}}',
            reason,
        )

    def window(self, days: int) -> None:
        reason = f"Your segment looks at the last {days} days"
        self.add(
            f"Purchases in the last {days} days",
            f"{{{{#each transactions where date in last {days} days}}}}\n" + _ROW + "\n{{else}}\nNothing yet.\n{{/each}}",
            reason,
        )
        self.add(f"Spent in the last {days} days", f"{{{{sum transactions.amount where date in last {days} days}}}}", reason)

    def unpaid(self, reason: str) -> None:
        self.add("Unpaid orders", "{{#each orders where paid = no}}\n{{date}} - {{items}} - {{currency}} {{amount}}\n{{/each}}", reason)
        self.add("Unpaid total", "{{stats.unpaid_order_total}}", reason)

    def undelivered(self, reason: str) -> None:
        self.add("Orders awaiting delivery", "{{#each orders where delivered = no}}\n{{date}} - {{items}} - due {{delivery_date}}\n{{/each}}", reason)
        self.add("Days until delivery", "{{latest_order.days_until_delivery}}", reason)


# --- visual-builder segments -------------------------------------------------


def _whole_number(value) -> int | None:
    """Filter values arrive as 30, 30.0 or "30" depending on where the
    segment was built."""
    try:
        n = float(value)
    except (TypeError, ValueError):
        return None
    return int(n) if n > 0 and n == int(n) else None


def _walk(node: dict):
    if node.get("type") == "group":
        for child in node.get("conditions", []):
            yield from _walk(child)
    else:
        yield node


def _from_filters(filters: dict, s: _Suggestions) -> None:
    for cond in _walk(filters or {}):
        field, op, value = cond.get("field", ""), cond.get("operator"), cond.get("value")
        if field.startswith("extra."):
            key = field[len("extra.") :]
            s.add(key, f"{{{{extra.{_slugify(key)}}}}}", f'Your segment filters on "{key}"')
        elif field == "interests":
            s.add("Interested in", "{{customer.interests}}", "Your segment filters on interests")
        elif field in ("job", "pet", "address"):
            s.add(field.capitalize(), f"{{{{customer.{field}}}}}", f"Your segment filters on {field}")
        elif field == "birthday":
            s.add("Age", "{{customer.age}}", "Your segment filters on birthdays")
            s.add("Days until birthday", "{{customer.days_until_birthday}}", "Your segment filters on birthdays")
            s.add("If birthday is within 30 days", "{{#if customer.days_until_birthday <= 30}}\nHappy early birthday!\n{{/if}}", "Your segment filters on birthdays")
        elif field in ("last_purchase_date", "first_purchase_date", "transaction_count", "total_spent"):
            s.purchases("Your segment filters on purchase history")
            days = _whole_number(value)
            if op == "within_last_days" and days:
                s.window(days)
            if op == "over_days_ago":
                s.add("Last items bought", "{{latest_transaction.items}}", "Your segment looks for customers who haven't bought lately")
            if field == "total_spent" and op == "greater_than" and value is not None:
                s.add(
                    "If lifetime spend is over the threshold",
                    f"{{{{#if stats.lifetime_spend > {value}}}}}\nAs one of our top customers…\n{{{{/if}}}}",
                    "Your segment filters on total spent",
                )
        elif field == "has_unpaid_order":
            s.unpaid("Your segment filters on unpaid orders")
        elif field in ("has_undelivered_order", "last_order_date", "order_count"):
            s.undelivered("Your segment filters on orders")
            s.add("Latest order items", "{{latest_order.items}}", "Your segment filters on orders")
        elif field == "created_at":
            s.add("Days as a customer", "{{customer.days_as_customer}}", "Your segment filters on when they joined")


# --- SQL segments -----------------------------------------------------------


def _from_sql(db: Session, org_id: UUID, sql: str, s: _Suggestions) -> None:
    try:
        tree = sqlglot.parse_one(sql, read="sqlite")
    except sqlglot.errors.SqlglotError:
        return
    tables = {t.name.lower() for t in tree.find_all(exp.Table)}
    columns = {c.name.lower() for c in tree.find_all(exp.Column)}
    orders_only = bool(tables & {"orders", "order_items"}) and not tables & {"transactions", "transaction_items"}

    for like in tree.find_all(exp.Like, exp.ILike):
        pattern = like.expression
        column = like.this.find(exp.Column) if isinstance(like.this, exp.Expression) else None
        if not isinstance(pattern, exp.Literal) or column is None:
            continue
        word = pattern.this.strip("%_ ").strip()
        if not word or "%" in word:
            continue
        if column.name.lower() in ("item", "items"):
            s.item(word, orders=orders_only)
        elif column.name.lower() == "interests":
            s.add("Interested in", "{{customer.interests}}", f'Your segment looks for "{word}" in interests')

    for literal in tree.find_all(exp.Literal):
        m = re.fullmatch(r"\s*-\s*(\d+)\s+days?\s*", str(literal.this))
        if m:
            s.window(int(m.group(1)))

    if tables & {"transactions", "transaction_items"}:
        s.purchases("Your segment uses purchase history")
    if "orders" in tables or "order_items" in tables:
        if "paid" in columns:
            s.unpaid("Your segment checks whether orders are paid")
        if "delivered" in columns or "delivery_date" in columns:
            s.undelivered("Your segment checks deliveries")

    for col, key in _custom_field_columns(list_custom_field_keys(db, org_id)):
        if col in columns:
            s.add(key, f"{{{{extra.{_slugify(key)}}}}}", f'Your segment uses the "{key}" field')
    if "birthday" in columns:
        s.add("Days until birthday", "{{customer.days_until_birthday}}", "Your segment uses birthdays")


def suggest_for_segment(db: Session, org_id: UUID, segment: Segment) -> list[dict]:
    s = _Suggestions()
    s.add("First name", "{{customer.first_name}}", "Personal greeting")
    if segment.sql:
        _from_sql(db, org_id, segment.sql, s)
    else:
        _from_filters(segment.filters, s)
    s.add("Business name", "{{business.name}}", "Sign-off")
    return s.items[:MAX_SUGGESTIONS]


def describe_segment(segment: Segment) -> str:
    """For the email-writing prompt."""
    if segment.sql:
        return f'Segment "{segment.name}", defined by this SQL:\n{segment.sql}'
    import json

    return f'Segment "{segment.name}", defined by these filters:\n{json.dumps(segment.filters)}'
