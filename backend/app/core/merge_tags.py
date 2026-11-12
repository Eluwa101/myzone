"""Resolves {{category.field}} placeholders in a message template against
one customer, at send time - never client-side, so what's actually in the
customer's inbox always reflects live data, not whatever was true when the
template was drafted.

Alongside the plain data fields (a customer's name, a business's phone
number, ...), this also computes arithmetic/date tags - lifetime spend,
days since last purchase, age, days until a delivery is due, and so on -
from the same underlying data, so a template can say "it's been {{stats.
days_since_last_purchase}} days" without the business having to compute
that themselves. These are plain Python functions, not a user-authorable
formula language: letting template text itself define arbitrary
expressions would be a code-execution surface, so for now new computed
tags are added here deliberately rather than self-served.

Money fields that sum across a customer's transactions/orders (lifetime
spend, unpaid total, ...) add up `amount` regardless of currency - fine for
the common case of one business trading in one currency, but a customer
who has been invoiced in more than one currency will get a number that
mixes them. Same simplification segment_controller's total_spent field
already makes.

Beyond single values there are list blocks and filtered totals, for
anything that is "some of this customer's rows" rather than one field:

    {{#each transactions where item contains "lighter" sort date desc limit 5}}
      {{date}} - {{items}} - {{currency}} {{amount}}
    {{else}}
      Nothing yet.
    {{/each}}

    {{count transactions where date in last 30 days}}
    {{sum transaction_items.amount where item contains "lighter"}}

And conditions, at the top level or per row inside a list:

    {{#if (count transactions where item contains "lighter") >= 3}}
      You're one of our regulars!
    {{else}}
      Come back soon.
    {{/if}}

    {{#if customer.days_until_birthday <= 30 and customer.email is set}}...{{/if}}
    {{#if any orders where paid = no}}...{{/if}}
    {{#each transactions}}{{items}}{{#if amount >= 10000}} (big one!){{/if}}{{/each}}

Collections: transactions, transaction_items (one row per line item),
orders, order_items. Conditions also take `between <a> and <b>`,
`is set` and `is not set`. #if blocks can't be nested inside other #if
blocks. This is a fixed grammar parsed by _parse_query below
- field names, a handful of comparison operators, sort and limit - not an
expression language, so there is still nothing here that executes
template-supplied code.

The catalog (`available_merge_tags`) is the single source of truth the
frontend's tag picker renders from, so the picker can never drift out of
sync with what the resolver actually understands."""
import html
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Callable
from uuid import UUID

from sqlalchemy.orm import Session

from app.controllers.segment_fields import list_custom_field_keys
from app.models.customer import Customer
from app.models.order import Order
from app.models.organization import Organization
from app.models.org_settings import OrgSettings
from app.models.transaction import Transaction

MISSING = "—"

TAG_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_]+)\.([a-zA-Z_]+)\s*\}\}")


@dataclass
class MergeTagContext:
    customer: Customer
    org: Organization
    org_settings: OrgSettings | None


def _latest(items: list, date_attr: str):
    dated = [i for i in items if getattr(i, date_attr, None)]
    return max(dated, key=lambda i: getattr(i, date_attr)) if dated else None


def _order_items_text(order: Order | None) -> str | None:
    if not order or not order.items:
        return None
    return ", ".join(f"{i['name']} x{float(i['qty']):g}" if i.get("qty", 1) != 1 else i["name"] for i in order.items)


def _tx_items_text(tx: Transaction | None) -> str | None:
    if not tx or not tx.items:
        return None
    return ", ".join(f"{i['item']} x{float(i['qty']):g}" if i.get("qty", 1) != 1 else i["item"] for i in tx.items)


def _money(value: float) -> str:
    return f"{value:,.2f}"


def _age_years(c: Customer) -> int | None:
    if not c.birthday:
        return None
    today = date.today()
    b = c.birthday
    return today.year - b.year - ((today.month, today.day) < (b.month, b.day))


def _days_until_birthday(c: Customer) -> int | None:
    if not c.birthday:
        return None
    today = date.today()
    b = c.birthday
    for year in (today.year, today.year + 1):
        try:
            occurrence = b.replace(year=year)
        except ValueError:
            occurrence = date(year, 2, 28)  # the birthday is Feb 29 and `year` isn't a leap year
        if occurrence >= today:
            return (occurrence - today).days
    return None  # unreachable - the loop always finds this year's or next year's occurrence


def _days_as_customer(c: Customer) -> int:
    return (date.today() - c.created_at.date()).days


def _lifetime_spend(c: Customer) -> float:
    return sum(float(t.amount or 0) for t in c.transactions)


def _average_transaction(c: Customer) -> float | None:
    if not c.transactions:
        return None
    return _lifetime_spend(c) / len(c.transactions)


def _purchase_dates(c: Customer) -> list[date]:
    return [t.date for t in c.transactions] + [o.order_date for o in c.orders]


def _days_since_last_purchase(c: Customer) -> int | None:
    dates = _purchase_dates(c)
    return (date.today() - max(dates)).days if dates else None


def _first_purchase_date(c: Customer) -> str | None:
    dates = _purchase_dates(c)
    return min(dates).isoformat() if dates else None


def _unpaid_order_total(c: Customer) -> float:
    return sum(float(o.amount or 0) for o in c.orders if not o.paid and o.amount is not None)


def _days_since_ordered(o: Order | None) -> int | None:
    return (date.today() - o.order_date).days if o else None


def _days_until_delivery(o: Order | None) -> int | None:
    return (o.delivery_date - date.today()).days if o and o.delivery_date else None


def _order_overdue(o: Order | None) -> str | None:
    if not o or not o.delivery_date:
        return None
    return "Yes" if (not o.delivered and date.today() > o.delivery_date) else "No"


def _days_since_transaction(t: Transaction | None) -> int | None:
    return (date.today() - t.date).days if t else None


_CUSTOMER_FIELDS: dict[str, tuple[str, Callable[[Customer], object]]] = {
    "name": ("Full name", lambda c: c.name),
    "first_name": ("First name", lambda c: c.first_name),
    "last_name": ("Last name", lambda c: c.last_name),
    "phone": ("Phone", lambda c: c.phone),
    "email": ("Email", lambda c: c.email),
    "job": ("Job", lambda c: c.job),
    "pet": ("Pet", lambda c: c.pet),
    "address": ("Address", lambda c: c.address),
    "birthday": ("Birthday", lambda c: c.birthday.isoformat() if c.birthday else None),
    "age": ("Age (years)", _age_years),
    "days_until_birthday": ("Days until next birthday", _days_until_birthday),
    "days_as_customer": ("Days as a customer", _days_as_customer),
    "interests": ("Interested in", lambda c: c.interests),
    "display_id": ("Customer ID", lambda c: c.display_id),
    "status": ("Status", lambda c: c.status.value if c.status else None),
}

_BUSINESS_FIELDS: dict[str, tuple[str, Callable[["MergeTagContext"], object]]] = {
    "name": ("Business name", lambda ctx: (ctx.org_settings.biz_name if ctx.org_settings else None) or ctx.org.name),
    "industry": ("Industry", lambda ctx: ctx.org_settings.industry if ctx.org_settings else None),
    "manager_name": ("Manager name", lambda ctx: ctx.org_settings.manager_name if ctx.org_settings else None),
    "phone": ("Business phone", lambda ctx: ctx.org_settings.phone if ctx.org_settings else None),
    "address": ("Business address", lambda ctx: ctx.org_settings.address if ctx.org_settings else None),
    "whatsapp_number": ("WhatsApp number", lambda ctx: ctx.org_settings.whatsapp_number if ctx.org_settings else None),
}

_LATEST_ORDER_FIELDS: dict[str, tuple[str, Callable[[Order | None], object]]] = {
    "date": ("Date", lambda o: o.order_date.isoformat() if o else None),
    "items": ("Items", lambda o: _order_items_text(o)),
    "amount": ("Amount", lambda o: o.amount if o else None),
    "currency": ("Currency", lambda o: o.currency if o else None),
    "delivered": ("Delivered?", lambda o: ("Yes" if o.delivered else "No") if o else None),
    "days_since_ordered": ("Days since ordered", _days_since_ordered),
    "days_until_delivery": ("Days until delivery due", _days_until_delivery),
    "overdue": ("Delivery overdue?", _order_overdue),
}

_LATEST_TRANSACTION_FIELDS: dict[str, tuple[str, Callable[[Transaction | None], object]]] = {
    "date": ("Date", lambda t: t.date.isoformat() if t else None),
    "items": ("Items", lambda t: _tx_items_text(t)),
    "amount": ("Amount", lambda t: t.amount if t else None),
    "currency": ("Currency", lambda t: t.currency if t else None),
    "days_since": ("Days since", _days_since_transaction),
}

_STATS_FIELDS: dict[str, tuple[str, Callable[[Customer], object]]] = {
    "lifetime_spend": ("Lifetime spend", lambda c: _money(_lifetime_spend(c))),
    "transaction_count": ("Number of transactions", lambda c: len(c.transactions)),
    "order_count": ("Number of orders", lambda c: len(c.orders)),
    "average_transaction": ("Average transaction", lambda c: (_money(_average_transaction(c)) if _average_transaction(c) is not None else None)),
    "days_since_last_purchase": ("Days since last purchase", _days_since_last_purchase),
    "first_purchase_date": ("First purchase date", _first_purchase_date),
    "pending_order_count": ("Orders awaiting delivery", lambda c: sum(1 for o in c.orders if not o.delivered)),
    "unpaid_order_total": ("Unpaid orders total", lambda c: _money(_unpaid_order_total(c))),
}

_SYSTEM_FIELDS: dict[str, tuple[str, Callable[[], object]]] = {
    "today": ("Today's date", lambda: date.today().isoformat()),
    "year": ("Current year", lambda: date.today().year),
}

_CATEGORIES = [
    ("customer", "Customer", _CUSTOMER_FIELDS),
    ("business", "Business", _BUSINESS_FIELDS),
    ("latest_order", "Latest order", _LATEST_ORDER_FIELDS),
    ("latest_transaction", "Latest transaction", _LATEST_TRANSACTION_FIELDS),
    ("stats", "Purchase stats", _STATS_FIELDS),
    ("system", "Date", _SYSTEM_FIELDS),
]


# --- list blocks and filtered totals ------------------------------------


class _QueryError(Exception):
    pass


_EACH_PATTERN = re.compile(r"\{\{\s*#each\s+(.*?)\}\}(.*?)\{\{\s*/each\s*\}\}", re.DOTALL)
_IF_PATTERN = re.compile(r"\{\{\s*#if\s+(.*?)\}\}(.*?)\{\{\s*/if\s*\}\}", re.DOTALL)
_ELSE_PATTERN = re.compile(r"\{\{\s*else\s*\}\}")
_AGGREGATE_FUNCS = ("count", "sum", "avg", "min", "max")
_AGGREGATE_PATTERN = re.compile(r"\{\{\s*(count|sum|avg|min|max)\s+(.*?)\}\}", re.DOTALL)
_ROW_TAG_PATTERN = re.compile(r"\{\{\s*([a-zA-Z_]+)\s*\}\}")
# quoted strings, brackets on their own, or runs of anything else
_TOKEN_PATTERN = re.compile(r'"[^"]*"|\'[^\']*\'|[()]|[^\s()]+')
_SYMBOL_OPS = {"=", "==", "!=", ">", ">=", "<", "<="}
_MONEY_FIELDS = {"amount", "price"}
_NUMERIC_FIELDS = {"amount", "price", "qty", "item_count"}
_DATE_FIELDS = {"date", "delivery_date"}
_YES_NO_WORDS = {"true": "yes", "false": "no"}

# what each list's rows have - must match _collection_rows below
_COLLECTION_FIELDS: dict[str, set[str]] = {
    "transactions": {"date", "items", "item", "amount", "currency", "item_count"},
    "transaction_items": {"date", "item", "qty", "amount", "currency"},
    "orders": {"date", "delivery_date", "items", "item", "amount", "currency", "paid", "delivered", "notes", "item_count"},
    "order_items": {"date", "delivery_date", "item", "qty", "price", "currency", "paid", "delivered"},
}

_ROW = "{{date}} - {{items}} - {{currency}} {{amount}}"
_LIST_SNIPPETS = [
    ("all_purchases", "List: all purchases", "{{#each transactions}}\n" + _ROW + "\n{{/each}}"),
    ("last_purchases", "List: last 3 purchases", "{{#each transactions limit 3}}\n" + _ROW + "\n{{/each}}"),
    (
        "purchases_of_item",
        "List: purchases containing an item (edit the word)",
        '{{#each transactions where item contains "rice"}}\n' + _ROW + "\n{{else}}\nNo purchases yet.\n{{/each}}",
    ),
    ("recent_purchases", "List: purchases in the last 30 days", "{{#each transactions where date in last 30 days}}\n" + _ROW + "\n{{/each}}"),
    ("big_purchases", "List: purchases above an amount", "{{#each transactions where amount >= 10000 sort amount desc}}\n" + _ROW + "\n{{/each}}"),
    ("line_items", "List: every item bought", "{{#each transaction_items}}\n{{date}} - {{item}} x{{qty}} - {{currency}} {{amount}}\n{{/each}}"),
    ("undelivered_orders", "List: orders awaiting delivery", "{{#each orders where delivered = no}}\n{{date}} - {{items}} - due {{delivery_date}}\n{{/each}}"),
    ("unpaid_orders", "List: unpaid orders", "{{#each orders where paid = no}}\n{{date}} - {{items}} - {{currency}} {{amount}}\n{{/each}}"),
    ("count_item", "Total: times they bought an item", '{{count transactions where item contains "rice"}}'),
    ("sum_item", "Total: spent on an item", '{{sum transaction_items.amount where item contains "rice"}}'),
    ("qty_item", "Total: quantity bought of an item", '{{sum transaction_items.qty where item contains "rice"}}'),
    ("sum_recent", "Total: spent in the last 30 days", "{{sum transactions.amount where date in last 30 days}}"),
    ("max_purchase", "Total: biggest single purchase", "{{max transactions.amount}}"),
    ("purchases_between_amounts", "List: purchases between two amounts", "{{#each transactions where amount between 1000 and 5000}}\n" + _ROW + "\n{{/each}}"),
    ("purchases_in_period", "List: purchases in a date range", "{{#each transactions where date between 2026-01-01 and 2026-12-31}}\n" + _ROW + "\n{{/each}}"),
    (
        "list_with_highlight",
        "List: last 5, starring big purchases",
        "{{#each transactions limit 5}}\n" + _ROW + "{{#if amount >= 10000}} ⭐{{/if}}\n{{/each}}",
    ),
]

_CONDITION_SNIPPETS = [
    (
        "if_bought_item",
        "If they bought an item (edit the word)",
        '{{#if any transactions where item contains "rice"}}\nThanks for buying rice from us!\n{{else}}\nHave you tried our rice?\n{{/if}}',
    ),
    ("if_regular", "If 3 or more purchases", "{{#if (count transactions) >= 3}}\nThank you for being one of our regulars!\n{{/if}}"),
    ("if_big_spender", "If lifetime spend is over an amount", "{{#if stats.lifetime_spend >= 50000}}\nAs one of our top customers…\n{{/if}}"),
    ("if_recent", "If they bought in the last 30 days", "{{#if any transactions where date in last 30 days}}\nThanks for your recent visit!\n{{else}}\nWe miss you!\n{{/if}}"),
    (
        "if_unpaid",
        "If they have an unpaid order",
        "{{#if any orders where paid = no}}\nA quick reminder: you have {{count orders where paid = no}} unpaid order(s).\n{{/if}}",
    ),
    ("if_birthday_soon", "If their birthday is within 30 days", "{{#if customer.days_until_birthday <= 30}}\nHappy early birthday!\n{{/if}}"),
    ("if_field_set", "If a field is filled in", "{{#if customer.phone is set}}\nWe can also reach you on {{customer.phone}}.\n{{/if}}"),
    ("if_spend_between", "If lifetime spend is in a range", "{{#if stats.lifetime_spend between 10000 and 50000}}\n…\n{{/if}}"),
]


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _collection_rows(customer: Customer, collection: str) -> list[dict]:
    """One flat dict per row. `item` on a whole transaction/order is all of
    its line items joined, so `where item contains "lighter"` means "any
    purchase that included a lighter"; on the *_items collections it is
    that one line."""
    if collection == "transactions":
        return [
            {
                "date": t.date,
                "items": _tx_items_text(t),
                "item": _tx_items_text(t),
                "amount": float(t.amount or 0),
                "currency": t.currency or "",
                "item_count": len(t.items or []),
            }
            for t in customer.transactions
        ]
    if collection == "transaction_items":
        return [
            {
                "date": t.date,
                "item": li.get("item") or "",
                "qty": float(li.get("qty") or 1),
                "amount": float(li.get("amount") or 0),
                "currency": t.currency or "",
            }
            for t in customer.transactions
            for li in (t.items or [])
        ]
    if collection == "orders":
        return [
            {
                "date": o.order_date,
                "delivery_date": o.delivery_date,
                "items": _order_items_text(o),
                "item": _order_items_text(o),
                "amount": float(o.amount) if o.amount is not None else None,
                "currency": o.currency or "",
                "paid": _yes_no(o.paid),
                "delivered": _yes_no(o.delivered),
                "notes": o.notes,
                "item_count": len(o.items or []),
            }
            for o in customer.orders
        ]
    if collection == "order_items":
        return [
            {
                "date": o.order_date,
                "delivery_date": o.delivery_date,
                "item": li.get("name") or "",
                "qty": float(li.get("qty") or 1),
                "price": float(li["price"]) if li.get("price") is not None else None,
                "currency": o.currency or "",
                "paid": _yes_no(o.paid),
                "delivered": _yes_no(o.delivered),
            }
            for o in customer.orders
            for li in (o.items or [])
        ]
    raise _QueryError(f"unknown collection {collection!r}")


def _clean_header(raw: str) -> str:
    """A block header typed in the rich-text editor arrives HTML-encoded
    (&gt;, &nbsp;), possibly with curly quotes or stray formatting tags."""
    text = html.unescape(re.sub(r"<[^>]+>", "", raw)).replace("\xa0", " ")
    for curly, plain in (("“", '"'), ("”", '"'), ("‘", "'"), ("’", "'")):
        text = text.replace(curly, plain)
    return text.strip()


def _tokenize(header: str) -> list[str]:
    return _TOKEN_PATTERN.findall(_clean_header(header))


def _unquote(token: str) -> str:
    return token[1:-1] if len(token) >= 2 and token[0] == token[-1] and token[0] in "\"'" else token


def _need(tokens: list[str], index: int) -> str:
    if index >= len(tokens):
        raise _QueryError("it ends too early")
    return tokens[index]


def _parse_condition(tokens: list[str], i: int) -> tuple[tuple, int]:
    """`<field> <op> <value>` starting at tokens[i] -> ((field, op, value), next i).
    Ops: contains, not contains, = / is, != / is not, >, >=, <, <=,
    between <a> and <b>, in last <n> days, is set, is not set / is empty."""
    field = _need(tokens, i).lower()
    op_token = _need(tokens, i + 1)
    op = op_token.lower()
    if op == "not" and _need(tokens, i + 2).lower() == "contains":
        return (field, "not contains", _unquote(_need(tokens, i + 3))), i + 4
    if op == "in" and _need(tokens, i + 2).lower() == "last":
        days = _need(tokens, i + 3)
        if not days.isdigit() or _need(tokens, i + 4).lower() not in ("day", "days"):
            raise _QueryError("expected `in last <number> days`")
        return (field, "in last days", int(days)), i + 5
    if op == "between":
        low = _unquote(_need(tokens, i + 2))
        if _need(tokens, i + 3).lower() != "and":
            raise _QueryError("expected `between <low> and <high>`")
        return (field, "between", (low, _unquote(_need(tokens, i + 4)))), i + 5
    if op == "is":
        nxt = _need(tokens, i + 2)
        if nxt.lower() == "set":
            return (field, "is set", None), i + 3
        if nxt.lower() == "empty":
            return (field, "is not set", None), i + 3
        if nxt.lower() == "not":
            after = _need(tokens, i + 3)
            if after.lower() == "set":
                return (field, "is not set", None), i + 4
            if after.lower() == "empty":
                return (field, "is set", None), i + 4
            return (field, "!=", _unquote(after)), i + 4
        return (field, "=", _unquote(nxt)), i + 3
    if op == "contains" or op in _SYMBOL_OPS:
        return (field, "=" if op == "==" else op, _unquote(_need(tokens, i + 2))), i + 3
    raise _QueryError(f"unknown comparison {op_token!r}")


def _parse_query_tokens(tokens: list[str]) -> dict:
    """`<collection>[.<field>] [where <cond> [and <cond>]...] [sort <field>
    [asc|desc]] [limit <n>]`."""
    if not tokens:
        raise _QueryError("it's empty")
    collection, _, field = tokens[0].partition(".")
    collection = collection.lower()
    if collection not in _COLLECTION_FIELDS:
        raise _QueryError(f"unknown list {tokens[0].split('.')[0]!r} - use one of: {', '.join(_COLLECTION_FIELDS)}")
    fields = _COLLECTION_FIELDS[collection]
    query: dict = {"collection": collection, "field": field.lower() or None, "conditions": [], "sort": None, "limit": None}

    def check_field(name: str) -> None:
        if name not in fields:
            raise _QueryError(f"{collection} has no field {name!r} - use one of: {', '.join(sorted(fields))}")

    if query["field"]:
        check_field(query["field"])
    i = 1
    while i < len(tokens):
        word = tokens[i].lower()
        if word in ("where", "and"):
            condition, i = _parse_condition(tokens, i + 1)
            check_field(condition[0])
            query["conditions"].append(condition)
        elif word == "sort":
            sort_field = _need(tokens, i + 1).lower()
            check_field(sort_field)
            direction = tokens[i + 2].lower() if i + 2 < len(tokens) and tokens[i + 2].lower() in ("asc", "desc") else None
            query["sort"] = (sort_field, direction or "asc")
            i += 3 if direction else 2
        elif word == "limit":
            if not _need(tokens, i + 1).isdigit():
                raise _QueryError("limit must be a number")
            query["limit"] = int(tokens[i + 1])
            i += 2
        else:
            raise _QueryError(f"didn't expect {tokens[i]!r} there")
    return query


def _parse_query(header: str) -> dict:
    return _parse_query_tokens(_tokenize(header))


def _as_number(value) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def _compare_values(actual, op: str, expected) -> bool:
    if op == "is set":
        return actual not in (None, "")
    if op == "is not set":
        return actual in (None, "")
    if op == "in last days":
        d = _as_date(actual)
        return d is not None and date.today() - timedelta(days=expected) <= d <= date.today()
    if actual in (None, ""):
        return False
    if op == "contains":
        return str(expected).casefold() in str(actual).casefold()
    if op == "not contains":
        return str(expected).casefold() not in str(actual).casefold()
    if op == "between":
        low, high = expected
        return _compare_values(actual, ">=", low) and _compare_values(actual, "<=", high)

    if isinstance(actual, (date, datetime)) or (_as_date(actual) is not None and _as_date(expected) is not None):
        left, right = _as_date(actual), _as_date(expected)
        if right is None:
            raise _QueryError(f"{expected!r} isn't a date (use YYYY-MM-DD)")
    elif _as_number(actual) is not None:
        left, right = _as_number(actual), _as_number(expected)
        if right is None:
            if op in ("=", "!="):
                left, right = str(actual).casefold(), str(expected).casefold()
            else:
                raise _QueryError(f"{expected!r} isn't a number")
    else:
        left, right = str(actual).casefold(), str(expected).casefold()
        if left in ("yes", "no"):
            right = _YES_NO_WORDS.get(right, right)
    return {"=": left == right, "!=": left != right, ">": left > right, ">=": left >= right, "<": left < right, "<=": left <= right}[op]


def _run_query(customer: Customer, query: dict) -> list[dict]:
    rows = _collection_rows(customer, query["collection"])
    rows = [r for r in rows if all(_compare_values(r[f], op, v) for f, op, v in query["conditions"])]
    sort_field, direction = query["sort"] or ("date", "desc")  # newest first unless told otherwise
    present = [r for r in rows if r[sort_field] is not None]
    present.sort(key=lambda r: r[sort_field], reverse=direction == "desc")
    rows = present + [r for r in rows if r[sort_field] is None]
    return rows[: query["limit"]] if query["limit"] is not None else rows


def _format_row_value(field: str, value) -> str:
    if value is None or value == "":
        return MISSING
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float):
        return _money(value) if field in _MONEY_FIELDS else f"{value:g}"
    return str(value)


def _aggregate_value(func: str, query: dict, customer: Customer):
    """The raw result of count/sum/avg/min/max - a number, a date, or None
    when there's nothing to take the min/max/avg of."""
    rows = _run_query(customer, query)
    if func == "count":
        return len(rows)
    field = query["field"]
    if not field:
        raise _QueryError(f"{func} needs a field, e.g. {query['collection']}.amount")
    if field not in _NUMERIC_FIELDS and not (func in ("min", "max") and field in _DATE_FIELDS):
        raise _QueryError(f"can't {func} {field}")
    values = [r[field] for r in rows if r[field] is not None]
    if func == "sum":
        return float(sum(values))
    if not values:
        return None
    if func == "avg":
        return float(sum(values)) / len(values)
    return (min if func == "min" else max)(values)


def _format_aggregate(func: str, query: dict, value) -> str:
    if func == "count":
        return str(value)
    return _format_row_value(query["field"], value)


def _render_aggregate(match: re.Match, customer: Customer) -> str:
    func = match.group(1)
    try:
        query = _parse_query(match.group(2))
        return _format_aggregate(func, query, _aggregate_value(func, query, customer))
    except _QueryError:
        return match.group(0)


# --- {{#if}} ---------------------------------------------------------------


def _parse_if(header: str) -> dict:
    """`<clause> [and|or <clause>]...` where a clause is one of:
        customer.age >= 18              (any single-value tag)
        (count transactions where ...) >= 3   (a total, in brackets)
        any transactions where ...      / no orders where ...  (must be last)
        amount > 5000                   (a field of the row - inside #each only)"""
    tokens = _tokenize(header)
    if not tokens:
        raise _QueryError("it's empty")
    clauses: list[dict] = []
    joiner = None
    i = 0
    while True:
        first = _need(tokens, i)
        lowered = first.lower()
        if lowered in ("any", "no"):
            query = _parse_query_tokens(tokens[i + 1 :])
            clauses.append({"kind": "exists", "negate": lowered == "no", "query": query})
            i = len(tokens)
        elif first == "(":
            depth, j = 0, i
            while j < len(tokens):
                depth += {"(": 1, ")": -1}.get(tokens[j], 0)
                if depth == 0:
                    break
                j += 1
            if j >= len(tokens):
                raise _QueryError("a bracket isn't closed")
            inner = tokens[i + 1 : j]
            if not inner or inner[0].lower() not in _AGGREGATE_FUNCS:
                raise _QueryError("brackets must hold a total, e.g. (count transactions)")
            func = inner[0].lower()
            query = _parse_query_tokens(inner[1:])
            # reuse the condition parser with a placeholder field name
            (_, op, value), i = _parse_condition(["_total", *tokens[j + 1 :]], 0)
            i += j  # _parse_condition counted from the placeholder
            clauses.append({"kind": "aggregate", "func": func, "query": query, "op": op, "value": value})
        else:
            (field, op, value), i = _parse_condition(tokens, i)
            if "." in field:
                category, _, key = field.partition(".")
                clauses.append({"kind": "tag", "category": category, "key": key, "op": op, "value": value})
            else:
                clauses.append({"kind": "row", "field": field, "op": op, "value": value})
        if i >= len(tokens):
            break
        word = tokens[i].lower()
        if word not in ("and", "or"):
            raise _QueryError(f"didn't expect {tokens[i]!r} there")
        if joiner and word != joiner:
            raise _QueryError("use either `and` or `or` in one #if, not both")
        joiner = word
        i += 1
    return {"clauses": clauses, "joiner": joiner or "and"}


def _evaluate_if(parsed: dict, ctx: "MergeTagContext", row: dict | None = None) -> bool:
    results = []
    for clause in parsed["clauses"]:
        kind = clause["kind"]
        if kind == "exists":
            found = bool(_run_query(ctx.customer, clause["query"]))
            results.append(not found if clause["negate"] else found)
        elif kind == "aggregate":
            value = _aggregate_value(clause["func"], clause["query"], ctx.customer)
            results.append(_compare_values(value, clause["op"], clause["value"]))
        elif kind == "tag":
            known, value = _tag_value(clause["category"], clause["key"], ctx)
            if not known:
                raise _QueryError(f"unknown tag {clause['category']}.{clause['key']}")
            results.append(_compare_values(value, clause["op"], clause["value"]))
        else:
            if row is None:
                raise _QueryError(f"{clause['field']!r} only works inside {{{{#each}}}}")
            if clause["field"] not in row:
                raise _QueryError(f"unknown field {clause['field']!r}")
            results.append(_compare_values(row[clause["field"]], clause["op"], clause["value"]))
    return all(results) if parsed["joiner"] == "and" else any(results)


def _split_else(body: str) -> tuple[str, str]:
    """Splits a block body at its own {{else}} - not one belonging to an
    {{#if}} nested inside it."""
    nested: list[str] = []

    def hide(m: re.Match) -> str:
        nested.append(m.group(0))
        return f"\x00{len(nested) - 1}\x00"

    masked = _IF_PATTERN.sub(hide, body)
    parts = _ELSE_PATTERN.split(masked, maxsplit=1)

    def restore(text: str) -> str:
        return re.sub(r"\x00(\d+)\x00", lambda m: nested[int(m.group(1))], text)

    return restore(parts[0]), restore(parts[1]) if len(parts) > 1 else ""


def _render_if(match: re.Match, ctx: "MergeTagContext", row: dict | None = None) -> str:
    try:
        parsed = _parse_if(match.group(1))
        if row is None and any(c["kind"] == "row" for c in parsed["clauses"]):
            return match.group(0)
        result = _evaluate_if(parsed, ctx, row)
    except _QueryError:
        return match.group(0)  # leave a condition we can't read visible rather than guess
    then_part, else_part = _split_else(match.group(2))
    return then_part if result else else_part


def _render_each(match: re.Match, ctx: "MergeTagContext", fmt: Callable[[str], str]) -> str:
    try:
        rows = _run_query(ctx.customer, _parse_query(match.group(1)))
    except _QueryError:
        return match.group(0)
    body, fallback = _split_else(match.group(2))
    if not rows:
        return fallback

    def render_row(number: int, row: dict) -> str:
        text = _IF_PATTERN.sub(lambda m: _render_if(m, ctx, row), body)

        def replace(m: re.Match) -> str:
            name = m.group(1).lower()
            if name == "number":
                return str(number)
            return fmt(_format_row_value(name, row[name])) if name in row else m.group(0)

        return _ROW_TAG_PATTERN.sub(replace, text)

    return "".join(render_row(n, row) for n, row in enumerate(rows, start=1))


# --- checking a template ----------------------------------------------------


def _short(text: str, limit: int = 60) -> str:
    text = " ".join(_clean_header(text).split())
    return text if len(text) <= limit else text[: limit - 1] + "…"


def find_merge_tag_problems(text: str, known_tags: set[str]) -> list[str]:
    """Plain-language problems with the merge tags in a subject/body -
    unknown tags, typos in list/condition blocks, unclosed blocks. Empty
    when everything will resolve. `known_tags` is the set of "category.key"
    single-value tags this org has (see known_tag_keys)."""
    problems: list[str] = []

    def add(problem: str) -> None:
        if problem not in problems:
            problems.append(problem)

    def check_if_header(header: str, row_fields: set[str] | None) -> None:
        try:
            parsed = _parse_if(header)
        except _QueryError as e:
            add(f"{{{{#if {_short(header)}}}}}: {e}.")
            return
        for clause in parsed["clauses"]:
            if clause["kind"] == "tag" and f"{clause['category']}.{clause['key']}" not in known_tags:
                add(f"{{{{#if {_short(header)}}}}}: unknown tag {clause['category']}.{clause['key']}.")
            if clause["kind"] == "aggregate" and clause["func"] != "count":
                field = clause["query"]["field"]
                if not field or (field not in _NUMERIC_FIELDS and not (clause["func"] in ("min", "max") and field in _DATE_FIELDS)):
                    add(f"{{{{#if {_short(header)}}}}}: {clause['func']} needs a number field, e.g. {clause['query']['collection']}.amount.")
            if clause["kind"] == "row":
                if row_fields is None:
                    add(f"{{{{#if {_short(header)}}}}}: {clause['field']!r} only works inside a {{{{#each}}}} list.")
                elif clause["field"] not in row_fields:
                    add(f"{{{{#if {_short(header)}}}}}: the list has no field {clause['field']!r}.")

    def check_each(m: re.Match) -> str:
        header, body = m.group(1), m.group(2)
        try:
            query = _parse_query(header)
        except _QueryError as e:
            add(f"{{{{#each {_short(header)}}}}}: {e}.")
            return ""
        fields = _COLLECTION_FIELDS[query["collection"]]

        def check_row_if(im: re.Match) -> str:
            check_if_header(im.group(1), fields)
            return _ELSE_PATTERN.sub("", im.group(2))

        body = _IF_PATTERN.sub(check_row_if, body)
        for rm in _ROW_TAG_PATTERN.finditer(body):
            name = rm.group(1).lower()
            if name not in fields and name not in ("number", "else"):
                add(f"{{{{{rm.group(1)}}}}} isn't a field of {query['collection']} - use one of: {', '.join(sorted(fields | {'number'}))}.")
        return _ELSE_PATTERN.sub("", _ROW_TAG_PATTERN.sub("", body))

    def check_if(m: re.Match) -> str:
        check_if_header(m.group(1), None)
        return _ELSE_PATTERN.sub("", m.group(2))

    work = _EACH_PATTERN.sub(check_each, text)
    work = _IF_PATTERN.sub(check_if, work)

    for pattern, message in (
        (r"\{\{\s*#each\b", "A {{#each}} list has no closing {{/each}}."),
        (r"\{\{\s*/each\s*\}\}", "There's a {{/each}} without a matching {{#each}}."),
        (r"\{\{\s*#if\b", "An {{#if}} has no closing {{/if}}."),
        (r"\{\{\s*/if\s*\}\}", "There's a {{/if}} without a matching {{#if}}."),
        (r"\{\{\s*else\s*\}\}", "There's an {{else}} outside any {{#each}} or {{#if}}."),
    ):
        if re.search(pattern, work):
            add(message)
            work = re.sub(pattern + (r".*?\}\}" if pattern.endswith(r"\b") else ""), "", work, flags=re.DOTALL)

    def check_aggregate(m: re.Match) -> str:
        func = m.group(1)
        try:
            query = _parse_query(m.group(2))
            if func != "count":
                field = query["field"]
                if not field:
                    raise _QueryError(f"{func} needs a field, e.g. {query['collection']}.amount")
                if field not in _NUMERIC_FIELDS and not (func in ("min", "max") and field in _DATE_FIELDS):
                    raise _QueryError(f"can't {func} {field}")
        except _QueryError as e:
            add(f"{{{{{func} {_short(m.group(2))}}}}}: {e}.")
        return ""

    work = _AGGREGATE_PATTERN.sub(check_aggregate, work)

    def check_tag(m: re.Match) -> str:
        if f"{m.group(1)}.{m.group(2)}" not in known_tags:
            add(f"Unknown tag {{{{{m.group(1)}.{m.group(2)}}}}}.")
        return ""

    work = TAG_PATTERN.sub(check_tag, work)
    for m in re.finditer(r"\{\{(.*?)\}\}", work, flags=re.DOTALL):
        add(f"Unknown tag {{{{{_short(m.group(1))}}}}}.")
    return problems


def _slugify(key: str) -> str:
    """Custom "extra" fields are free text (spaces, punctuation, any case),
    but a merge tag's key has to be a plain identifier - this turns one into
    the other, consistently, so the same slug is produced both when the
    catalog is built and when a tag is resolved."""
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", key.strip()).strip("_").lower()
    return slug or "field"


def available_merge_tags(db: Session, org_id: UUID) -> list[dict]:
    """The full catalog for this org right now - the fixed categories above,
    plus one "extra.<field>" tag per custom field any of this org's
    customers currently has. Nothing is hardcoded for custom fields: a
    field created tomorrow (via CSV import, the agent, or a customer's Info
    tab) just appears here the next time this is called, with no code
    change needed."""
    tags = [
        {"category": category, "category_label": category_label, "key": key, "label": label, "tag": f"{{{{{category}.{key}}}}}"}
        for category, category_label, fields in _CATEGORIES
        for key, (label, _getter) in fields.items()
    ]

    tags.extend(
        {"category": "lists", "category_label": "Lists & totals", "key": key, "label": label, "tag": snippet}
        for key, label, snippet in _LIST_SNIPPETS
    )
    tags.extend(
        {"category": "conditions", "category_label": "Conditions", "key": key, "label": label, "tag": snippet}
        for key, label, snippet in _CONDITION_SNIPPETS
    )

    seen_slugs: set[str] = set()
    for extra_key in list_custom_field_keys(db, org_id):
        slug = base_slug = _slugify(extra_key)
        i = 2
        while slug in seen_slugs:
            slug, i = f"{base_slug}_{i}", i + 1
        seen_slugs.add(slug)
        tags.append({"category": "extra", "category_label": "Custom fields", "key": slug, "label": extra_key, "tag": f"{{{{extra.{slug}}}}}"})

    return tags


def _tag_value(category: str, key: str, ctx: MergeTagContext) -> tuple[bool, object]:
    """(known?, raw value) for one single-value tag like customer.first_name."""
    if category == "customer" and key in _CUSTOMER_FIELDS:
        return True, _CUSTOMER_FIELDS[key][1](ctx.customer)
    if category == "business" and key in _BUSINESS_FIELDS:
        return True, _BUSINESS_FIELDS[key][1](ctx)
    if category == "latest_order" and key in _LATEST_ORDER_FIELDS:
        return True, _LATEST_ORDER_FIELDS[key][1](_latest(ctx.customer.orders, "order_date"))
    if category == "latest_transaction" and key in _LATEST_TRANSACTION_FIELDS:
        return True, _LATEST_TRANSACTION_FIELDS[key][1](_latest(ctx.customer.transactions, "date"))
    if category == "stats" and key in _STATS_FIELDS:
        return True, _STATS_FIELDS[key][1](ctx.customer)
    if category == "system" and key in _SYSTEM_FIELDS:
        return True, _SYSTEM_FIELDS[key][1]()
    if category == "extra":
        return True, next((v for k, v in (ctx.customer.extra or {}).items() if _slugify(k) == key), None)
    return False, None


def known_tag_keys(db: Session, org_id: UUID) -> set[str]:
    """"category.key" for every single-value tag this org can use."""
    keys = set()
    for t in available_merge_tags(db, org_id):
        m = TAG_PATTERN.fullmatch(t["tag"])
        if m:
            keys.add(f"{m.group(1)}.{m.group(2)}")
    return keys


_PLACEHOLDER_PATTERN = re.compile(r"\[([A-Za-z][A-Za-z0-9 _\-/'&.]{0,40})\]")


def find_placeholders(*texts: str) -> list[str]:
    """Fill-in-the-blank markers like [discount] or [link] - what the
    assistant writes instead of inventing a fact. Sending one as-is would
    put "[discount]" in front of every customer, so they're flagged."""
    found: list[str] = []
    for text in texts:
        for m in _PLACEHOLDER_PATTERN.finditer(html.unescape(text or "")):
            if m.group(0) not in found:
                found.append(m.group(0))
    return found


def merge_tag_problems(db: Session, org_id: UUID, *texts: str) -> list[str]:
    known = known_tag_keys(db, org_id)
    problems: list[str] = []
    for text in texts:
        for p in find_merge_tag_problems(text or "", known):
            if p not in problems:
                problems.append(p)
    return problems


def resolve_merge_tags(text: str, ctx: MergeTagContext, escape: bool = False) -> str:
    """escape=True HTML-escapes every substituted value - use it for an
    HTML body, so a customer name or item containing < or & can't break
    (or inject into) the markup; leave it off for a plain-text subject."""
    if not text or "{{" not in text:
        return text

    fmt: Callable[[str], str] = html.escape if escape else (lambda v: v)
    has_blocks = re.search(r"\{\{\s*#(each|if)\b", text) is not None

    # lists first (each row can hold its own #if), then top-level #if,
    # then totals, then single values - so every later step sees the
    # text the earlier ones produced
    text = _EACH_PATTERN.sub(lambda m: _render_each(m, ctx, fmt), text)
    text = _IF_PATTERN.sub(lambda m: _render_if(m, ctx), text)
    if has_blocks:
        # in the rich-text editor each block line sits in a paragraph of
        # its own, which is left behind empty
        text = text.replace("<p></p>", "").replace("<p><br></p>", "")
    text = _AGGREGATE_PATTERN.sub(lambda m: _render_aggregate(m, ctx.customer), text)

    def replace(match: re.Match) -> str:
        known, value = _tag_value(match.group(1), match.group(2), ctx)
        if not known:
            return match.group(0)  # unknown tag - leave it as-is rather than guess
        return fmt(str(value)) if value not in (None, "") else MISSING

    return TAG_PATTERN.sub(replace, text)


MERGE_TAG_GUIDE = """Merge tags are filled in per customer when the email is sent.

Single values: {{category.key}}, e.g. {{customer.first_name}}, {{stats.lifetime_spend}}. Missing values show as "—".

Lists - repeat a block once per matching row:
  {{#each <list> [where <condition> [and <condition>]...] [sort <field> asc|desc] [limit <n>]}}
    ...row fields like {{date}} {{items}} {{amount}}; {{number}} is 1, 2, 3...
  {{else}}
    ...shown when nothing matches (optional)
  {{/each}}
  Lists and their row fields:
    transactions: date, items, item, amount, currency, item_count   (item = all items of that purchase, as text)
    transaction_items: date, item, qty, amount, currency            (one row per item bought)
    orders: date, delivery_date, items, item, amount, currency, paid (Yes/No), delivered (Yes/No), notes, item_count
    order_items: date, delivery_date, item, qty, price, currency, paid, delivered
  Default order is newest first.

Totals: {{count <list> [where ...]}}, {{sum <list>.<number field> [where ...]}}, also avg, min, max.
  e.g. {{count transactions where item contains "lighter"}}, {{sum transaction_items.amount where item contains "lighter"}}

Conditions (in where and #if):
  <field> contains "word" | not contains "word" | = value | != value | > n | >= n | < n | <= n
  <field> between <low> and <high> | <field> in last <n> days | <field> is set | <field> is not set
  Dates are YYYY-MM-DD. Put text values in double quotes.

If blocks:
  {{#if <condition>}} ... {{else}} ... {{/if}}
  A condition is one of:
    a single value:  customer.days_until_birthday <= 30, stats.lifetime_spend >= 50000, customer.email is set
    a total in brackets:  (count transactions where item contains "lighter") >= 3
    any/no rows:  any orders where paid = no   /   no transactions where date in last 60 days   (must come last)
    inside a list only, a row field:  {{#each transactions}}...{{#if amount >= 10000}}big!{{/if}}...{{/each}}
  Join conditions with `and` or with `or` (not both). An #if cannot contain another #if."""
