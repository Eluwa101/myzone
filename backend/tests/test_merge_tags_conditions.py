"""#if blocks, `between`, the tag checker behind Preview, per-segment tag
suggestions, and the assistant that writes emails."""
from datetime import date, timedelta

import pytest

from app.agent import email_draft


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _preview(client, auth_headers, customer_id, body_html, subject="x"):
    resp = client.post(
        "/api/messages/preview",
        json={"customer_id": customer_id, "subject": subject, "body_html": body_html},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def _body(client, auth_headers, customer_id, body_html):
    return _preview(client, auth_headers, customer_id, body_html)["body_html"]


@pytest.fixture
def ada(client, auth_headers):
    customer = client.post(
        "/api/customers", json={"first_name": "Ada", "last_name": "Obi", "email": "ada@x.com", "extra": {"Shoe Size": "42"}}, headers=auth_headers
    ).json()
    for days, item, amount in ((100, "Rice", 5000), (40, "Gas Lighter", 1000), (5, "lighter", 15000)):
        client.post(
            f"/api/customers/{customer['id']}/transactions",
            json={"date": _days_ago(days), "items": [{"item": item, "amount": amount}], "currency": "NGN"},
            headers=auth_headers,
        )
    client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": _days_ago(2), "items": [{"name": "Oil"}], "amount": 3000, "paid": False, "delivered": False},
        headers=auth_headers,
    )
    return customer["id"]


# --- #if ---------------------------------------------------------------------


@pytest.mark.parametrize(
    "condition, expected",
    [
        ("customer.first_name = Ada", True),
        ('customer.first_name = "ada"', True),
        ("customer.first_name != Ada", False),
        ("customer.email is set", True),
        ("customer.phone is set", False),
        ("customer.phone is not set", True),
        ("customer.phone is empty", True),
        ("stats.lifetime_spend >= 21000", True),  # "21,000.00" compares as a number
        ("stats.lifetime_spend > 21000", False),
        ("stats.lifetime_spend between 20000 and 30000", True),
        ("stats.transaction_count = 3", True),
        ("extra.shoe_size = 42", True),
        ('extra.shoe_size contains "4"', True),
        ("(count transactions) >= 3", True),
        ('(count transactions where item contains "lighter") = 2', True),
        ('(sum transaction_items.amount where item contains "lighter") > 15000', True),
        ("(max transactions.amount) between 10000 and 20000", True),
        ("(min transactions.date) < " + _days_ago(99), True),
        ("any orders where paid = no", True),
        ("no orders where paid = no", False),
        ("any transactions where date in last 30 days", True),
        ("no transactions where date in last 3 days", True),
        ("customer.email is set and stats.transaction_count > 5", False),
        ("customer.phone is set or stats.transaction_count = 3", True),
        ('customer.email is set and any transactions where item contains "rice" and amount > 1000', True),
    ],
)
def test_if_conditions(client, auth_headers, ada, condition, expected):
    body = _body(client, auth_headers, ada, f"{{{{#if {condition}}}}}YES{{{{else}}}}NO{{{{/if}}}}")
    assert body == ("YES" if expected else "NO"), condition


def test_if_without_else_and_with_tags_inside(client, auth_headers, ada):
    body = _body(client, auth_headers, ada, "{{#if any orders where paid = no}}Hi {{customer.first_name}}, {{count orders where paid = no}} unpaid{{/if}}!")
    assert body == "Hi Ada, 1 unpaid!"
    assert _body(client, auth_headers, ada, "A{{#if customer.phone is set}}B{{/if}}C") == "AC"


def test_if_around_a_list_and_a_list_with_its_own_if(client, auth_headers, ada):
    body = _body(
        client,
        auth_headers,
        ada,
        "{{#if (count transactions) > 0}}"
        "{{#each transactions sort amount desc}}{{items}}{{#if amount >= 10000}}*{{else}}.{{/if}};{{else}}none{{/each}}"
        "{{else}}no purchases{{/if}}",
    )
    assert body == "lighter*;Rice.;Gas Lighter.;"


def test_row_if_can_check_customer_tags_and_totals_too(client, auth_headers, ada):
    body = _body(client, auth_headers, ada, "{{#each transactions limit 1}}{{#if customer.first_name = Ada}}ok{{/if}}{{/each}}")
    assert body == "ok"


def test_if_in_rich_text_paragraphs(client, auth_headers, ada):
    body = _body(client, auth_headers, ada, "<p>Hi</p><p>{{#if stats.lifetime_spend &gt;= 1000}}</p><p>VIP</p><p>{{else}}</p><p>Regular</p><p>{{/if}}</p><p>Bye</p>")
    assert body == "<p>Hi</p><p>VIP</p><p>Bye</p>"


@pytest.mark.parametrize(
    "bad",
    [
        "{{#if customer.nonsense = 1}}x{{/if}}",
        "{{#if amount > 5}}x{{/if}}",  # row field outside a list
        "{{#if (count invoices) > 1}}x{{/if}}",
        "{{#if (count transactions) > lots}}x{{/if}}",
        "{{#if (count transactions > 1}}x{{/if}}",
        "{{#if customer.email is set and customer.phone is set or stats.order_count > 1}}x{{/if}}",
        "{{#if}}x{{/if}}",
    ],
)
def test_unreadable_ifs_are_left_visible(client, auth_headers, ada, bad):
    assert _body(client, auth_headers, ada, bad) == bad


# --- between ------------------------------------------------------------------


def test_between_in_lists_and_totals(client, auth_headers, ada):
    assert _body(client, auth_headers, ada, "{{#each transactions where amount between 1000 and 5000 sort amount asc}}{{items}};{{/each}}") == "Gas Lighter;Rice;"
    assert _body(client, auth_headers, ada, f"{{{{count transactions where date between {_days_ago(50)} and {_days_ago(1)}}}}}") == "2"


def test_new_list_fields_are_checked(client, auth_headers, ada):
    """Unknown fields are now caught even when the customer has no rows."""
    other = client.post("/api/customers", json={"name": "Empty"}, headers=auth_headers).json()["id"]
    bad = "{{#each transactions where colour = red}}x{{/each}}"
    assert _body(client, auth_headers, other, bad) == bad


# --- the checker behind Preview ---------------------------------------------


def test_preview_reports_no_problems_for_good_tags(client, auth_headers, ada):
    resp = _preview(
        client,
        auth_headers,
        ada,
        "{{#each transactions where amount between 1 and 9 limit 2}}{{number}} {{items}}{{#if amount > 1}}!{{/if}}{{else}}-{{/each}}"
        "{{#if any orders where paid = no}}{{extra.shoe_size}}{{/if}}{{count transactions}}",
        subject="Hi {{customer.first_name}}",
    )
    assert resp["problems"] == []


@pytest.mark.parametrize(
    "body, expected_fragment",
    [
        ("{{customer.firstname}}", "Unknown tag {{customer.firstname}}"),
        ("{{extra.hat_size}}", "Unknown tag {{extra.hat_size}}"),
        ("{{#each transactions}}{{colour}}{{/each}}", "{{colour}} isn't a field of transactions"),
        ("{{#each invoices}}x{{/each}}", "unknown list 'invoices'"),
        ("{{#each transactions where colour = red}}x{{/each}}", "transactions has no field 'colour'"),
        ("{{#each transactions}}x", "has no closing {{/each}}"),
        ("x{{/if}}", "{{/if}} without a matching {{#if}}"),
        ("{{#if amount > 5}}x{{/if}}", "only works inside a {{#each}} list"),
        ("{{#if customer.nope = 1}}x{{/if}}", "unknown tag customer.nope"),
        ("{{sum transactions.items}}", "can't sum items"),
        ("{{sum transactions}}", "sum needs a field"),
        ("{{#if (sum transactions) > 1}}x{{/if}}", "sum needs a number field"),
        ("{{greeting}}", "Unknown tag {{greeting}}"),
    ],
)
def test_preview_reports_problems(client, auth_headers, ada, body, expected_fragment):
    problems = _preview(client, auth_headers, ada, body)["problems"]
    assert any(expected_fragment in p for p in problems), problems


def test_subject_problems_are_reported_too(client, auth_headers, ada):
    assert any("customer.nam" in p for p in _preview(client, auth_headers, ada, "x", subject="Hi {{customer.nam}}")["problems"])


def test_every_catalog_snippet_is_problem_free_and_resolves(client, auth_headers, ada):
    tags = client.get("/api/messages/merge-tags", headers=auth_headers).json()
    assert any(t["category"] == "conditions" for t in tags)
    for t in tags:
        resp = _preview(client, auth_headers, ada, t["tag"])
        assert resp["problems"] == [], (t["tag"], resp["problems"])
        assert "{{" not in resp["body_html"], t["tag"]


# --- suggestions per segment -------------------------------------------------


def _suggested(client, auth_headers, segment_id):
    resp = client.get(f"/api/messages/merge-tags/suggested?segment_id={segment_id}", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_suggestions_for_a_sql_segment(client, auth_headers, ada):
    sql = """SELECT c.id FROM customers c JOIN transaction_items ti ON ti.customer_id = c.id
             WHERE LOWER(ti.item) LIKE '%lighter%' AND ti.date >= date('now', '-90 days') AND c.shoe_size = '42'"""
    segment = client.post("/api/segments", json={"name": "Lighters", "sql": sql}, headers=auth_headers).json()
    suggestions = _suggested(client, auth_headers, segment["id"])
    tags = [s["tag"] for s in suggestions]
    assert tags[0] == "{{customer.first_name}}"
    assert '{{count transactions where item contains "lighter"}}' in tags
    assert any(t.startswith("{{#each transactions where date in last 90 days}}") for t in tags)
    assert "{{extra.shoe_size}}" in tags
    assert all(s["reason"] for s in suggestions)
    # every suggestion works for a real customer
    for s in suggestions:
        resp = _preview(client, auth_headers, ada, s["tag"])
        assert resp["problems"] == [] and "{{" not in resp["body_html"], s["tag"]


def test_suggestions_for_a_filter_segment(client, auth_headers, ada):
    filters = {
        "type": "group",
        "combinator": "and",
        "conditions": [
            {"type": "condition", "field": "has_unpaid_order", "operator": "equals", "value": True},
            {"type": "condition", "field": "last_purchase_date", "operator": "within_last_days", "value": 30},
            {"type": "condition", "field": "extra.Shoe Size", "operator": "is_set"},
        ],
    }
    segment = client.post("/api/segments", json={"name": "Owing", "filters": filters}, headers=auth_headers).json()
    tags = [s["tag"] for s in _suggested(client, auth_headers, segment["id"])]
    assert "{{stats.unpaid_order_total}}" in tags
    assert "{{sum transactions.amount where date in last 30 days}}" in tags
    assert "{{extra.shoe_size}}" in tags
    assert tags[-1] == "{{business.name}}"


def test_suggestions_unknown_segment_404s(client, auth_headers):
    resp = client.get("/api/messages/merge-tags/suggested?segment_id=00000000-0000-0000-0000-000000000000", headers=auth_headers)
    assert resp.status_code == 404


# --- the assistant writing emails --------------------------------------------


class _Result:
    def __init__(self, content):
        self.content = content


def _scripted_model(monkeypatch, replies):
    seen: list[list[dict]] = []

    class _Model:
        def invoke(self, messages):
            seen.append(list(messages))
            return _Result(replies[len(seen) - 1])

    monkeypatch.setattr(email_draft, "get_model", lambda: _Model())
    monkeypatch.setattr(email_draft, "call_with_fallback", lambda get_model_fn, invoke: invoke(get_model_fn()))
    return seen


def test_draft_email_with_segment_context(client, auth_headers, ada, monkeypatch):
    segment = client.post(
        "/api/segments", json={"name": "Lighters", "sql": "SELECT customer_id FROM transaction_items WHERE item LIKE '%lighter%'"}, headers=auth_headers
    ).json()
    reply = (
        '```json\n{"subject": "Thanks {{customer.first_name}}!", "body_html": "<p>You bought '
        '{{count transactions where item contains \\"lighter\\"}} lighters.</p><script>alert(1)</script>"}\n```'
    )
    seen = _scripted_model(monkeypatch, [reply])
    resp = client.post(
        "/api/messages/draft",
        json={"description": "thank lighter buyers", "segment_id": segment["id"], "format": "designed"},
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    draft = resp.json()
    assert draft["subject"] == "Thanks {{customer.first_name}}!"
    assert "<script" not in draft["body_html"]
    assert draft["problems"] == []
    system = seen[0][0]["content"]
    assert "Lighters" in system and "{{extra.shoe_size}}" in system and "#each" in system and "role=\"presentation\"" in system
    assert 'item contains "lighter"' in system  # a segment suggestion


def test_draft_email_gets_one_chance_to_fix_bad_tags(client, auth_headers, monkeypatch):
    bad = '{"subject": "Hi", "body_html": "<p>{{customer.firstname}}</p>"}'
    good = '{"subject": "Hi", "body_html": "<p>{{customer.first_name}}</p>"}'
    seen = _scripted_model(monkeypatch, [bad, good])
    draft = client.post("/api/messages/draft", json={"description": "say hi"}, headers=auth_headers).json()
    assert draft["body_html"] == "<p>{{customer.first_name}}</p>"
    assert draft["problems"] == []
    assert "customer.firstname" in seen[1][-1]["content"]


def test_draft_email_returns_remaining_problems(client, auth_headers, monkeypatch):
    bad = '{"subject": "Hi", "body_html": "<p>{{customer.firstname}}</p>"}'
    _scripted_model(monkeypatch, [bad, bad])
    draft = client.post("/api/messages/draft", json={"description": "say hi"}, headers=auth_headers).json()
    assert draft["problems"] == ["Unknown tag {{customer.firstname}}."]


def test_draft_email_edits_the_current_email(client, auth_headers, monkeypatch):
    seen = _scripted_model(monkeypatch, ['{"subject": "S", "body_html": "<p>B</p>"}'])
    client.post(
        "/api/messages/draft",
        json={"description": "make it shorter", "current_subject": "Old", "current_body": "<p>Old body</p>"},
        headers=auth_headers,
    )
    user = seen[0][1]["content"]
    assert "Old body" in user and "make it shorter" in user


def test_draft_email_unusable_reply_is_422(client, auth_headers, monkeypatch):
    _scripted_model(monkeypatch, ["Sure! Here's your email.", "still not json"])
    assert client.post("/api/messages/draft", json={"description": "x"}, headers=auth_headers).status_code == 422


def test_preview_and_draft_report_placeholders(client, auth_headers, ada, monkeypatch):
    resp = _preview(client, auth_headers, ada, "<p>Get [discount] off at [link]. Array[0] isn't one.</p>", subject="[Shop] news")
    assert resp["placeholders"] == ["[Shop]", "[discount]", "[link]"]
    _scripted_model(monkeypatch, ['{"subject": "Hi", "body_html": "<p>[discount] off</p>"}'])
    draft = client.post("/api/messages/draft", json={"description": "promo"}, headers=auth_headers).json()
    assert draft["placeholders"] == ["[discount]"]
