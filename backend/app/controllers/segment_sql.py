"""Custom SQL segments, run in a throwaway sandbox - never on the real
database.

Each run copies ONE org's customers, transactions and orders into a fresh
in-memory SQLite database, runs the user's query there, and discards it.
Nothing else is ever in that database - no other business, no logins, no
password hashes - so a query, however clever, can only ever see the data
of the business that wrote it. That is the core guarantee, and it doesn't
depend on the checks below being perfect.

The checks are defence in depth and friendlier errors:
- sqlglot parses the query first: exactly one SELECT, only known tables.
- SQLite's authorizer allows only reads (no ATTACH, no writes, no
  PRAGMA), and blocks a few functions that could allocate huge amounts
  of memory.
- A progress handler stops any query running longer than QUERY_TIMEOUT_SECONDS.
- String/blob size is capped, and the returned ids are matched back
  against this org's real customers, so a query that invents an id
  (e.g. SELECT '<someone else's id>' AS id) matches nothing.

Copying the data on every run is fine at small-business scale (hundreds
or a few thousand customers - milliseconds), and the visual builder
already loads the same rows into memory to evaluate filters."""
import re
import sqlite3
import time
from datetime import date, datetime
from uuid import UUID

import sqlglot
from sqlglot import exp
from sqlalchemy.orm import Session, joinedload

from app.controllers.segment_fields import list_custom_field_keys
from app.models.customer import Customer

QUERY_TIMEOUT_SECONDS = 2.0
MAX_SQL_LENGTH = 5000
MAX_VALUE_BYTES = 1_000_000

ALLOWED_TABLES = ("customers", "transactions", "transaction_items", "orders", "order_items")

_FORBIDDEN_NODES = tuple(
    getattr(exp, name)
    for name in (
        "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "Command", "Pragma", "Attach", "Detach",
        "Transaction", "Commit", "Rollback", "Set", "Use", "Copy", "LoadData", "Analyze",
    )
    if hasattr(exp, name)
)

# functions that can read files, load code, or allocate unbounded memory
_FORBIDDEN_FUNCTIONS = {"load_extension", "readfile", "writefile", "edit", "fts3_tokenizer", "randomblob", "zeroblob"}

_ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
    getattr(sqlite3, "SQLITE_RECURSIVE", 33),
}


class SegmentSQLError(Exception):
    """The message is shown to the user as-is."""


# --- the sandbox's tables ---------------------------------------------------
#
# (column, sqlite type, description). Dates are 'YYYY-MM-DD' text so they
# compare correctly and work with SQLite's date() functions; yes/no flags
# are 0/1.

_BASE_COLUMNS: dict[str, list[tuple[str, str, str]]] = {
    "customers": [
        ("id", "TEXT", "Customer id - your query must return this"),
        ("display_id", "TEXT", "Customer ID shown in the app, e.g. CR001"),
        ("name", "TEXT", "Full name"),
        ("first_name", "TEXT", ""),
        ("last_name", "TEXT", ""),
        ("email", "TEXT", ""),
        ("phone", "TEXT", ""),
        ("status", "TEXT", "lead, customer or inactive"),
        ("job", "TEXT", ""),
        ("nationality", "TEXT", ""),
        ("pet", "TEXT", ""),
        ("birthday", "TEXT", "YYYY-MM-DD"),
        ("address", "TEXT", ""),
        ("interests", "TEXT", ""),
        ("notes", "TEXT", ""),
        ("consent_date", "TEXT", "YYYY-MM-DD, empty if no recorded consent"),
        ("created_at", "TEXT", "Date added, YYYY-MM-DD"),
    ],
    "transactions": [
        ("id", "TEXT", ""),
        ("customer_id", "TEXT", "-> customers.id"),
        ("date", "TEXT", "YYYY-MM-DD"),
        ("amount", "REAL", "Total of all line items"),
        ("currency", "TEXT", ""),
        ("item_count", "INTEGER", "Number of line items"),
        ("items", "TEXT", 'All items as text, e.g. "Rice, Gas Lighter x2"'),
    ],
    "transaction_items": [
        ("transaction_id", "TEXT", "-> transactions.id"),
        ("customer_id", "TEXT", "-> customers.id"),
        ("date", "TEXT", "YYYY-MM-DD"),
        ("item", "TEXT", "Item name"),
        ("qty", "REAL", ""),
        ("amount", "REAL", "Line total"),
        ("currency", "TEXT", ""),
    ],
    "orders": [
        ("id", "TEXT", ""),
        ("customer_id", "TEXT", "-> customers.id"),
        ("order_date", "TEXT", "YYYY-MM-DD"),
        ("delivery_date", "TEXT", "YYYY-MM-DD, may be empty"),
        ("amount", "REAL", "May be empty"),
        ("currency", "TEXT", ""),
        ("paid", "INTEGER", "1 = paid, 0 = unpaid"),
        ("delivered", "INTEGER", "1 = delivered, 0 = not yet"),
        ("notes", "TEXT", ""),
        ("items", "TEXT", "All items as text"),
    ],
    "order_items": [
        ("order_id", "TEXT", "-> orders.id"),
        ("customer_id", "TEXT", "-> customers.id"),
        ("order_date", "TEXT", "YYYY-MM-DD"),
        ("item", "TEXT", "Item name"),
        ("qty", "REAL", ""),
        ("price", "REAL", "May be empty"),
        ("paid", "INTEGER", "1 = paid, 0 = unpaid"),
        ("delivered", "INTEGER", "1 = delivered, 0 = not yet"),
    ],
}


def _slug(key: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", key.strip()).strip("_").lower()
    if not slug or slug[0].isdigit():
        slug = f"f_{slug}"
    return slug


def _custom_field_columns(custom_keys: list[str]) -> list[tuple[str, str]]:
    """(column name, original key) for each custom field - prefixed with
    extra_ only when its name would clash with a built-in column."""
    taken = {c for c, _, _ in _BASE_COLUMNS["customers"]}
    out = []
    for key in custom_keys:
        col = base = _slug(key)
        if col in taken:
            col = base = f"extra_{base}"
        n = 2
        while col in taken:
            col, n = f"{base}_{n}", n + 1
        taken.add(col)
        out.append((col, key))
    return out


def sandbox_schema(db: Session, org_id: UUID) -> list[dict]:
    """The tables a query can use - shown in the SQL editor as a reference
    and given to the assistant when it writes a query."""
    custom = _custom_field_columns(list_custom_field_keys(db, org_id))
    tables = []
    for table, columns in _BASE_COLUMNS.items():
        cols = [{"name": c, "type": t, "description": d} for c, t, d in columns]
        if table == "customers":
            cols += [{"name": c, "type": "TEXT", "description": f'Custom field "{key}"'} for c, key in custom]
        tables.append({"name": table, "columns": cols})
    return tables


def schema_as_text(schema: list[dict]) -> str:
    lines = []
    for t in schema:
        cols = ", ".join(f"{c['name']} {c['type']}" + (f" ({c['description']})" if c["description"] else "") for c in t["columns"])
        lines.append(f"{t['name']}({cols})")
    return "\n".join(lines)


# --- validation -------------------------------------------------------------


def validate_sql(sql: str) -> str:
    """Returns the query, cleaned up (trailing semicolon dropped), or raises
    SegmentSQLError with a message fit to show the user."""
    sql = (sql or "").strip().rstrip(";").strip()
    if not sql:
        raise SegmentSQLError("Write a query first.")
    if len(sql) > MAX_SQL_LENGTH:
        raise SegmentSQLError(f"That query is too long (limit {MAX_SQL_LENGTH} characters).")
    try:
        statements = [s for s in sqlglot.parse(sql, read="sqlite") if s is not None]
    except sqlglot.errors.SqlglotError as e:
        first_line = str(e).splitlines()[0] if str(e) else "syntax error"
        raise SegmentSQLError(f"Couldn't read that SQL: {first_line}") from e
    if len(statements) != 1:
        raise SegmentSQLError("Only one query is allowed.")
    statement = statements[0]
    if not isinstance(statement, exp.Query) or any(isinstance(node, _FORBIDDEN_NODES) for node in statement.walk()):
        raise SegmentSQLError("Only SELECT queries are allowed.")

    cte_names = {cte.alias_or_name.lower() for cte in statement.find_all(exp.CTE)}
    for table in statement.find_all(exp.Table):
        if not isinstance(table.this, exp.Identifier):
            continue  # a table-valued function such as json_each(...)
        if table.args.get("db") or table.args.get("catalog"):
            raise SegmentSQLError(f"Unknown table {table.sql(dialect='sqlite')!r}.")
        name = table.name.lower()
        if name not in ALLOWED_TABLES and name not in cte_names:
            raise SegmentSQLError(f"Unknown table {table.name!r}. You can use: {', '.join(ALLOWED_TABLES)}.")
    for func in statement.find_all(exp.Anonymous, exp.Func):
        name = (func.name if isinstance(func, exp.Anonymous) else func.sql_name()).lower()
        if name in _FORBIDDEN_FUNCTIONS:
            raise SegmentSQLError(f"The function {name}() isn't allowed.")
    return sql


# --- the sandbox ------------------------------------------------------------


def _iso(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _items_text(items: list, name_key: str) -> str:
    def one(i: dict) -> str:
        qty = i.get("qty", 1)
        return f"{i.get(name_key) or ''} x{float(qty):g}" if qty not in (None, 1) else (i.get(name_key) or "")

    return ", ".join(one(i) for i in items or [])


def _build_sandbox(db: Session, org_id: UUID) -> tuple[sqlite3.Connection, set[str]]:
    customers = (
        db.query(Customer)
        .options(joinedload(Customer.transactions), joinedload(Customer.orders))
        .filter(Customer.org_id == org_id)
        .all()
    )
    custom = _custom_field_columns(list_custom_field_keys(db, org_id))

    conn = sqlite3.connect(":memory:")
    for table, columns in _BASE_COLUMNS.items():
        cols = [f'"{c}" {t}' for c, t, _ in columns]
        if table == "customers":
            cols += [f'"{c}" TEXT' for c, _ in custom]
        conn.execute(f'CREATE TABLE "{table}" ({", ".join(cols)})')

    customer_rows, tx_rows, tx_item_rows, order_rows, order_item_rows = [], [], [], [], []
    for c in customers:
        cid = str(c.id)
        extra = c.extra or {}
        customer_rows.append(
            (
                cid, c.display_id, c.name, c.first_name, c.last_name, c.email, c.phone,
                c.status.value if c.status else None, c.job, c.nationality, c.pet, _iso(c.birthday), c.address,
                c.interests, c.notes, _iso(c.consent_date), _iso(c.created_at),
                *(None if extra.get(key) is None else str(extra.get(key)) for _, key in custom),
            )
        )
        for t in c.transactions:
            tid = str(t.id)
            tx_rows.append((tid, cid, _iso(t.date), float(t.amount or 0), t.currency or "", len(t.items or []), _items_text(t.items, "item")))
            for li in t.items or []:
                tx_item_rows.append((tid, cid, _iso(t.date), li.get("item") or "", float(li.get("qty") or 1), float(li.get("amount") or 0), t.currency or ""))
        for o in c.orders:
            oid = str(o.id)
            order_rows.append(
                (
                    oid, cid, _iso(o.order_date), _iso(o.delivery_date), float(o.amount) if o.amount is not None else None,
                    o.currency or "", int(bool(o.paid)), int(bool(o.delivered)), o.notes, _items_text(o.items, "name"),
                )
            )
            for li in o.items or []:
                order_item_rows.append(
                    (
                        oid, cid, _iso(o.order_date), li.get("name") or "", float(li.get("qty") or 1),
                        float(li["price"]) if li.get("price") is not None else None, int(bool(o.paid)), int(bool(o.delivered)),
                    )
                )

    for table, rows in (
        ("customers", customer_rows),
        ("transactions", tx_rows),
        ("transaction_items", tx_item_rows),
        ("orders", order_rows),
        ("order_items", order_item_rows),
    ):
        if rows:
            conn.executemany(f'INSERT INTO "{table}" VALUES ({", ".join("?" * len(rows[0]))})', rows)
    conn.commit()
    return conn, {str(c.id) for c in customers}


def _lock_down(conn: sqlite3.Connection) -> None:
    """From here on the connection can only read. Installed after the
    tables are filled, before the user's query runs."""

    def authorizer(action, arg1, arg2, _db_name, _trigger):
        if action not in _ALLOWED_ACTIONS:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_FUNCTION and (arg2 or "").lower() in _FORBIDDEN_FUNCTIONS:
            return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    conn.set_authorizer(authorizer)
    conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_VALUE_BYTES)
    conn.setlimit(sqlite3.SQLITE_LIMIT_ATTACHED, 0)


def _execute(conn: sqlite3.Connection, sql: str) -> list[str]:
    """Runs the query on an already-built, locked-down sandbox and returns
    the customer ids it selected."""
    deadline = time.monotonic() + QUERY_TIMEOUT_SECONDS
    conn.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 1000)
    try:
        cursor = conn.execute(sql)
        names = [d[0].lower() for d in cursor.description or []]
        if "id" in names:
            index = names.index("id")
        elif len(names) == 1:
            index = 0
        else:
            raise SegmentSQLError("Your query must return the customer id, e.g. SELECT c.id FROM customers c ...")
        ids: list[str] = []
        while batch := cursor.fetchmany(1000):
            ids.extend(str(row[index]) for row in batch if row[index] is not None)
        return ids
    except sqlite3.OperationalError as e:
        if "interrupted" in str(e).lower():
            raise SegmentSQLError(f"That query took longer than {QUERY_TIMEOUT_SECONDS:g} seconds - try simplifying it.") from e
        if "not authorized" in str(e).lower():
            raise SegmentSQLError("That query tries to do something other than read data, which isn't allowed.") from e
        raise SegmentSQLError(f"SQL error: {e}") from e
    except sqlite3.Error as e:
        raise SegmentSQLError(f"SQL error: {e}") from e


def run_sql_segment(db: Session, org_id: UUID, sql: str) -> list[Customer]:
    sql = validate_sql(sql)
    conn, org_customer_ids = _build_sandbox(db, org_id)
    try:
        _lock_down(conn)
        ids = _execute(conn, sql)
    finally:
        conn.close()

    wanted = list(dict.fromkeys(i for i in ids if i in org_customer_ids))  # de-duplicated, query's order kept
    if not wanted:
        return []
    by_id = {str(c.id): c for c in db.query(Customer).filter(Customer.org_id == org_id, Customer.id.in_([UUID(i) for i in wanted])).all()}
    return [by_id[i] for i in wanted if i in by_id]
