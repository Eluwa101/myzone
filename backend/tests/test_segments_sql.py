"""Custom SQL segments - the sandbox, its guard rails, and the endpoints."""
from datetime import date, timedelta

import pytest

from app.agent import segment_suggest
from app.controllers import segment_sql
from app.controllers.segment_sql import SegmentSQLError, validate_sql


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _customer(client, auth_headers, name, **extra):
    return client.post("/api/customers", json={"name": name, **extra}, headers=auth_headers).json()


def _buy(client, auth_headers, customer_id, days_ago, *items):
    resp = client.post(
        f"/api/customers/{customer_id}/transactions",
        json={"date": _days_ago(days_ago), "items": [{"item": i, "amount": 1000} for i in items], "currency": "NGN"},
        headers=auth_headers,
    )
    assert resp.status_code == 201


def _preview(client, auth_headers, sql):
    return client.post("/api/segments/sql/preview", json={"sql": sql}, headers=auth_headers)


def _names(resp):
    assert resp.status_code == 200, resp.text
    return sorted(m["name"] for m in resp.json()["members"])


def _other_org_headers(client):
    from tests.conftest import verify_user_email

    client.post("/api/auth/signup", json={"org_name": "Other Co", "email": "sqlother@example.com", "password": "secret123"})
    verify_user_email("sqlother@example.com")
    token = client.post("/api/auth/login", json={"email": "sqlother@example.com", "password": "secret123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def shoppers(client, auth_headers):
    ada = _customer(client, auth_headers, "Ada Obi", extra={"Favorite Color": "Blue"})
    bo = _customer(client, auth_headers, "Bo Chen")
    _customer(client, auth_headers, "Cy Never")
    for days in (5, 20, 70):
        _buy(client, auth_headers, ada["id"], days, "Gas Lighter")
    _buy(client, auth_headers, ada["id"], 10, "Cooking Gas")
    _buy(client, auth_headers, bo["id"], 3, "lighter", "Rice")
    return {"ada": ada, "bo": bo}


# --- the cases the visual builder can't express -----------------------------


def test_bought_item_n_times_in_window(client, auth_headers, shoppers):
    sql = """
        SELECT c.id FROM customers c
        JOIN transaction_items ti ON ti.customer_id = c.id
        WHERE LOWER(ti.item) LIKE '%lighter%' AND ti.date >= date('now', '-90 days')
        GROUP BY c.id HAVING COUNT(*) >= 3
    """
    assert _names(_preview(client, auth_headers, sql)) == ["Ada Obi"]


def test_bought_x_but_never_y_and_never_bought_anything(client, auth_headers, shoppers):
    bought_lighter_never_gas = """
        SELECT id FROM customers WHERE id IN (SELECT customer_id FROM transaction_items WHERE LOWER(item) LIKE '%lighter%')
        AND id NOT IN (SELECT customer_id FROM transaction_items WHERE LOWER(item) LIKE '%gas%' AND LOWER(item) NOT LIKE '%lighter%');
    """
    assert _names(_preview(client, auth_headers, bought_lighter_never_gas)) == ["Bo Chen"]
    never_bought = "SELECT id FROM customers WHERE id NOT IN (SELECT customer_id FROM transactions)"
    assert _names(_preview(client, auth_headers, never_bought)) == ["Cy Never"]


def test_cte_and_custom_field_column(client, auth_headers, shoppers):
    sql = "WITH blue AS (SELECT id FROM customers WHERE favorite_color = 'Blue') SELECT id FROM blue"
    assert _names(_preview(client, auth_headers, sql)) == ["Ada Obi"]


def test_order_of_results_is_kept_and_duplicates_dropped(client, auth_headers, shoppers):
    sql = "SELECT c.id FROM customers c JOIN transactions t ON t.customer_id = c.id ORDER BY c.name DESC"
    resp = _preview(client, auth_headers, sql)
    assert [m["name"] for m in resp.json()["members"]] == ["Bo Chen", "Ada Obi"]


def test_single_unnamed_column_is_accepted(client, auth_headers, shoppers):
    assert _names(_preview(client, auth_headers, "SELECT customer_id FROM transactions WHERE items LIKE '%Rice%'")) == ["Bo Chen"]


def test_schema_lists_tables_and_custom_fields(client, auth_headers, shoppers):
    schema = client.get("/api/segments/sql/schema", headers=auth_headers).json()
    assert [t["name"] for t in schema] == ["customers", "transactions", "transaction_items", "orders", "order_items"]
    customer_cols = {c["name"] for c in schema[0]["columns"]}
    assert {"id", "name", "status", "favorite_color"} <= customer_cols


def test_custom_field_that_clashes_with_a_built_in_column_is_prefixed(client, auth_headers):
    _customer(client, auth_headers, "Ada Obi", extra={"Email": "work@x.com"})
    schema = client.get("/api/segments/sql/schema", headers=auth_headers).json()
    assert "extra_email" in {c["name"] for c in schema[0]["columns"]}


# --- isolation --------------------------------------------------------------


def test_only_this_orgs_data_is_in_the_sandbox(client, auth_headers, shoppers):
    other = _other_org_headers(client)
    stranger = _customer(client, other, "Stranger Danger")

    # the other org's customer isn't there to find
    assert _names(_preview(client, auth_headers, "SELECT id FROM customers")) == ["Ada Obi", "Bo Chen", "Cy Never"]
    # and inventing their id doesn't reach them either
    assert _names(_preview(client, auth_headers, f"SELECT '{stranger['id']}' AS id")) == []
    # the other org sees only its own
    assert _names(_preview(client, other, "SELECT id FROM customers")) == ["Stranger Danger"]


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM customers",
        "UPDATE customers SET name = 'x'",
        "INSERT INTO customers (id) VALUES ('x')",
        "DROP TABLE customers",
        "SELECT id FROM customers; DELETE FROM customers",
        "ATTACH DATABASE 'evil.db' AS evil",
        "PRAGMA table_info(customers)",
        "SELECT id FROM users",
        "SELECT id FROM main.customers",
        "SELECT id FROM sqlite_master",
        "SELECT load_extension('x') AS id",
        "SELECT hex(randomblob(1000000000)) AS id",
        "not even sql at all (",
        "",
    ],
)
def test_rejected_queries(client, auth_headers, shoppers, sql):
    resp = client.post("/api/segments/sql/preview", json={"sql": sql or " "}, headers=auth_headers)
    assert resp.status_code == 422
    # the customers are all still there afterwards
    assert len(_names(_preview(client, auth_headers, "SELECT id FROM customers"))) == 3


def test_query_without_an_id_column_is_rejected(client, auth_headers, shoppers):
    resp = _preview(client, auth_headers, "SELECT name, email FROM customers")
    assert resp.status_code == 422
    assert "customer id" in resp.json()["detail"]


def test_runaway_query_is_stopped(client, auth_headers, shoppers, monkeypatch):
    monkeypatch.setattr(segment_sql, "QUERY_TIMEOUT_SECONDS", 0.3)
    sql = "WITH RECURSIVE n(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM n) SELECT x AS id FROM n WHERE x < 0"
    resp = _preview(client, auth_headers, sql)
    assert resp.status_code == 422
    assert "took longer" in resp.json()["detail"]


def test_huge_strings_are_capped(client, auth_headers, shoppers):
    # doubling a string until it's enormous hits the size cap with an error
    doubling = "WITH RECURSIVE r(x) AS (SELECT 'x' UNION ALL SELECT x || x FROM r LIMIT 40) SELECT x AS id FROM r"
    assert _preview(client, auth_headers, doubling).status_code == 422
    # and SQLite's printf gives up quietly (NULL) instead of allocating 100MB
    assert _names(_preview(client, auth_headers, "SELECT printf('%.*c', 100000000, 'x') AS id")) == []


def test_authorizer_blocks_writes_even_if_validation_were_skipped(db_session_factory=None):
    """Defence in depth: the sandbox connection itself refuses anything but
    reads, independently of validate_sql."""
    import sqlite3

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE customers (id TEXT)")
    conn.execute("INSERT INTO customers VALUES ('a')")
    segment_sql._lock_down(conn)
    for sql in ("DELETE FROM customers", "ATTACH DATABASE ':memory:' AS x", "PRAGMA writable_schema = 1", "CREATE TABLE t (x)"):
        with pytest.raises(SegmentSQLError):
            segment_sql._execute(conn, sql)
    assert segment_sql._execute(conn, "SELECT id FROM customers") == ["a"]


def test_validate_sql_cleans_trailing_semicolon():
    assert validate_sql("  SELECT id FROM customers;  ") == "SELECT id FROM customers"
    with pytest.raises(SegmentSQLError):
        validate_sql("x" * 6000)


# --- saving SQL segments ----------------------------------------------------


def test_save_sql_segment_and_resolve_members(client, auth_headers, shoppers):
    sql = "SELECT customer_id FROM transaction_items WHERE LOWER(item) LIKE '%lighter%'"
    created = client.post("/api/segments", json={"name": "Lighter buyers", "sql": sql}, headers=auth_headers)
    assert created.status_code == 201
    segment = created.json()
    assert segment["sql"] == sql

    members = client.get(f"/api/segments/{segment['id']}/members", headers=auth_headers)
    assert _names(members) == ["Ada Obi", "Bo Chen"]

    # blank SQL switches back to the visual filters (empty = everyone)
    updated = client.patch(f"/api/segments/{segment['id']}", json={"sql": ""}, headers=auth_headers)
    assert updated.json()["sql"] is None
    assert len(_names(client.get(f"/api/segments/{segment['id']}/members", headers=auth_headers))) == 3


def test_saving_invalid_sql_is_rejected(client, auth_headers):
    resp = client.post("/api/segments", json={"name": "Bad", "sql": "DELETE FROM customers"}, headers=auth_headers)
    assert resp.status_code == 422
    assert client.get("/api/segments", headers=auth_headers).json() == []


def test_filter_segments_still_work_and_have_no_sql(client, auth_headers, shoppers):
    created = client.post("/api/segments", json={"name": "Everyone"}, headers=auth_headers).json()
    assert created["sql"] is None
    assert len(_names(client.get(f"/api/segments/{created['id']}/members", headers=auth_headers))) == 3


# --- the assistant ----------------------------------------------------------


class _FakeResult:
    def __init__(self, content):
        self.content = content


def _fake_model(monkeypatch, reply, seen=None):
    def call(get_model_fn, invoke):
        if seen is not None:
            seen.append(invoke)
        return _FakeResult(reply)

    monkeypatch.setattr(segment_suggest, "get_model", lambda: None)
    monkeypatch.setattr(segment_suggest, "call_with_fallback", call)


def test_suggest_sql_returns_a_validated_query(client, auth_headers, shoppers, monkeypatch):
    _fake_model(monkeypatch, "```sql\nSELECT c.id FROM customers c WHERE c.favorite_color = 'Blue';\n```")
    resp = client.post("/api/segments/sql/suggest", json={"description": "people who like blue"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["sql"] == "SELECT c.id FROM customers c WHERE c.favorite_color = 'Blue'"


def test_suggest_sql_refuses_unsafe_output(client, auth_headers, monkeypatch):
    _fake_model(monkeypatch, "DELETE FROM customers")
    resp = client.post("/api/segments/sql/suggest", json={"description": "delete everyone"}, headers=auth_headers)
    assert resp.status_code == 422


def test_suggest_sql_gets_the_orgs_schema_and_current_query(client, auth_headers, shoppers, monkeypatch):
    captured = {}

    class _Model:
        def invoke(self, messages):
            captured["messages"] = messages
            return _FakeResult("SELECT id FROM customers")

    monkeypatch.setattr(segment_suggest, "get_model", lambda: _Model())
    monkeypatch.setattr(segment_suggest, "call_with_fallback", lambda get_model_fn, invoke: invoke(get_model_fn()))
    client.post(
        "/api/segments/sql/suggest",
        json={"description": "only leads", "current_sql": "SELECT id FROM customers"},
        headers=auth_headers,
    )
    system, user = captured["messages"][0]["content"], captured["messages"][1]["content"]
    assert "favorite_color" in system and "transaction_items" in system
    assert "Current query" in user and "only leads" in user


def test_sql_endpoints_require_auth(client):
    assert client.get("/api/segments/sql/schema").status_code == 401
    assert client.post("/api/segments/sql/preview", json={"sql": "SELECT 1"}).status_code == 401
