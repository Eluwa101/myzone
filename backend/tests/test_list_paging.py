"""Optional ?search= / ?page= / ?page_size= on the list endpoints.

The endpoints are public API and keep returning plain arrays: without `page`
everything comes back as before, with it a slice, and either way the total
number of matching rows is in the X-Total-Count header."""

import uuid

import pytest

from app.core.security import create_access_token, hash_password
from app.models.custom_form import FormSubmission
from app.models.customer import Customer
from app.models.organization import Organization
from app.models.outbound_message import MessageChannel, MessageStatus, OutboundMessage
from app.models.user import User
from app.models.webhook import WebhookDelivery

TOTAL = "x-total-count"


def _ids(rows):
    return [r["id"] for r in rows]


def _walk_pages(client, headers, url, page_size, **params):
    """Fetch every page; returns (all rows in order, total from header)."""
    rows, page, total = [], 1, None
    while True:
        resp = client.get(url, params={**params, "page": page, "page_size": page_size}, headers=headers)
        assert resp.status_code == 200
        total = int(resp.headers[TOTAL])
        chunk = resp.json()
        rows += chunk
        if not chunk or len(rows) >= total:
            return rows, total
        page += 1


def _assert_clean_paging(client, headers, url, expected_total, page_size=2, **params):
    """No page overlaps another and none is missed; header total is right."""
    unpaged = client.get(url, params=params, headers=headers)
    assert unpaged.status_code == 200
    assert int(unpaged.headers[TOTAL]) == expected_total
    assert len(unpaged.json()) == expected_total
    rows, total = _walk_pages(client, headers, url, page_size, **params)
    assert total == expected_total
    assert len(rows) == expected_total
    assert len(set(_ids(rows))) == expected_total  # no duplicates across pages
    assert set(_ids(rows)) == set(_ids(unpaged.json()))  # nothing missed
    assert _ids(rows) == _ids(unpaged.json())  # same stable order
    past_end = client.get(url, params={**params, "page": 99, "page_size": page_size}, headers=headers)
    assert past_end.json() == []
    assert int(past_end.headers[TOTAL]) == expected_total


@pytest.fixture
def other_headers(db_session):
    org = Organization(name="Someone Else's Store")
    db_session.add(org)
    db_session.flush()
    user = User(org_id=org.id, email="other@example.com", hashed_password=hash_password("supersecret"), email_verified=True)
    db_session.add(user)
    db_session.commit()
    return {"Authorization": f"Bearer {create_access_token(user.id, org.id)}"}


@pytest.fixture
def org_id(client, auth_headers, db_session):
    return db_session.query(User).filter(User.email == "ada@example.com").first().org_id


def _customer(client, headers, name):
    return client.post("/api/customers", json={"name": name}, headers=headers).json()


# --- orders ---------------------------------------------------------------


def test_orders_paging_and_search(client, auth_headers):
    ada = _customer(client, auth_headers, "Ada Obi")
    bayo = _customer(client, auth_headers, "Bayo Ade")
    for i in range(5):
        client.post(
            f"/api/customers/{ada['id']}/orders",
            json={"order_date": f"2026-11-0{i + 1}", "items": [{"name": f"Rice {i}", "qty": 1}], "notes": "gift wrap" if i == 0 else None},
            headers=auth_headers,
        )
    client.post(f"/api/customers/{bayo['id']}/orders", json={"order_date": "2026-11-09", "items": [{"name": "Beans"}]}, headers=auth_headers)

    _assert_clean_paging(client, auth_headers, "/api/orders", 6)
    _assert_clean_paging(client, auth_headers, "/api/orders", 5, search="ada obi")
    assert len(client.get("/api/orders", params={"search": "beans"}, headers=auth_headers).json()) == 1  # item name
    assert len(client.get("/api/orders", params={"search": "GIFT"}, headers=auth_headers).json()) == 1  # notes, any case
    assert client.get("/api/orders", params={"search": "nomatch"}, headers=auth_headers).headers[TOTAL] == "0"
    # filters still compose with paging
    assert client.get("/api/orders", params={"pending": "true", "page": 1, "page_size": 2}, headers=auth_headers).headers[TOTAL] == "6"


def test_orders_search_treats_percent_literally(client, auth_headers):
    ada = _customer(client, auth_headers, "Ada Obi")
    client.post(f"/api/customers/{ada['id']}/orders", json={"order_date": "2026-11-01", "items": [{"name": "Rice"}]}, headers=auth_headers)
    assert client.get("/api/orders", params={"search": "%"}, headers=auth_headers).headers[TOTAL] == "0"


def test_orders_isolated_between_orgs(client, auth_headers, other_headers):
    ada = _customer(client, auth_headers, "Ada Obi")
    client.post(f"/api/customers/{ada['id']}/orders", json={"order_date": "2026-11-01", "items": [{"name": "Rice"}]}, headers=auth_headers)
    resp = client.get("/api/orders", headers=other_headers)
    assert resp.json() == []
    assert resp.headers[TOTAL] == "0"
    assert client.get("/api/orders", params={"search": "rice"}, headers=other_headers).json() == []


# --- notes ----------------------------------------------------------------


def test_notes_paging_search_and_detail(client, auth_headers, other_headers):
    ada = _customer(client, auth_headers, "Ada Obi")
    for i in range(5):
        client.post(
            "/api/notes",
            json={"title": f"Note {i}", "content": "creditor, owes money" if i == 0 else "plain", "customer_ids": [ada["id"]] if i < 2 else []},
            headers=auth_headers,
        )
    _assert_clean_paging(client, auth_headers, "/api/notes", 5)
    assert client.get("/api/notes", params={"search": "creditor"}, headers=auth_headers).headers[TOTAL] == "1"  # content
    assert client.get("/api/notes", params={"search": "note 3"}, headers=auth_headers).headers[TOTAL] == "1"  # title
    # linked customer's name, without duplicating a note per matching customer
    by_customer = client.get("/api/notes", params={"search": "ada"}, headers=auth_headers)
    assert by_customer.headers[TOTAL] == "2"
    assert len(by_customer.json()) == 2
    assert client.get("/api/notes", params={"customer_id": ada["id"], "page": 1, "page_size": 1}, headers=auth_headers).headers[TOTAL] == "2"

    note = client.get("/api/notes", headers=auth_headers).json()[0]
    detail = client.get(f"/api/notes/{note['id']}", headers=auth_headers)
    assert detail.status_code == 200
    assert detail.json()["content"] == note["content"]
    assert client.get(f"/api/notes/{note['id']}", headers=other_headers).status_code == 404
    assert client.get("/api/notes/00000000-0000-0000-0000-000000000000", headers=auth_headers).status_code == 404
    assert client.get("/api/notes", headers=other_headers).json() == []


# --- forms + submissions ---------------------------------------------------

CORE = [
    {"key": "first_name", "label": "First name", "type": "text", "required": True, "category": "customer"},
    {"key": "last_name", "label": "Last name", "type": "text", "required": False, "category": "customer"},
    {"key": "phone", "label": "Phone", "type": "tel", "required": False, "category": "customer"},
    {"key": "email", "label": "Email", "type": "email", "required": False, "category": "customer"},
]


def test_forms_paging_search_and_submissions(client, auth_headers, other_headers, db_session, org_id):
    forms = [client.post("/api/forms", json={"name": n, "fields": CORE}, headers=auth_headers).json() for n in ["Lead intake", "Lead survey", "Orders", "Feedback", "Events"]]
    _assert_clean_paging(client, auth_headers, "/api/forms", 5)
    _assert_clean_paging(client, auth_headers, "/api/forms", 2, search="LEAD", page_size=1)
    assert client.get("/api/forms", headers=other_headers).json() == []

    form = forms[0]
    customer = Customer(org_id=org_id, name="Sub Mitter", display_id="CR900")
    db_session.add(customer)
    db_session.flush()
    for _ in range(5):
        db_session.add(FormSubmission(form_id=uuid.UUID(form["id"]), org_id=org_id, customer_id=customer.id, raw_payload={"first_name": "Sub"}))
    db_session.commit()
    _assert_clean_paging(client, auth_headers, f"/api/forms/{form['id']}/submissions", 5)
    assert client.get(f"/api/forms/{form['id']}/submissions", headers=other_headers).status_code == 404


# --- segments ---------------------------------------------------------------


def test_segments_paging_and_search(client, auth_headers, other_headers):
    flt = {"type": "group", "combinator": "and", "conditions": [{"type": "condition", "field": "status", "operator": "equals", "value": "lead"}]}
    for name in ["Leads", "Big spenders", "Lapsed leads", "VIPs", "Events"]:
        assert client.post("/api/segments", json={"name": name, "filters": flt}, headers=auth_headers).status_code == 201
    _assert_clean_paging(client, auth_headers, "/api/segments", 5)
    _assert_clean_paging(client, auth_headers, "/api/segments", 2, search="leads", page_size=1)
    assert client.get("/api/segments", headers=other_headers).json() == []


# --- webhooks + deliveries --------------------------------------------------


def test_webhooks_paging_search_and_deliveries(client, auth_headers, other_headers, db_session, org_id):
    subs = [
        client.post("/api/webhooks", json={"target_url": f"https://{host}/hook", "event_types": ["customer.created"]}, headers=auth_headers).json()
        for host in ["zapier.com", "make.com", "example.com", "n8n.io", "zapier.net"]
    ]
    _assert_clean_paging(client, auth_headers, "/api/webhooks", 5)
    _assert_clean_paging(client, auth_headers, "/api/webhooks", 2, search="ZAPIER", page_size=1)
    assert client.get("/api/webhooks", headers=other_headers).json() == []

    sub = subs[0]
    for i in range(7):
        db_session.add(WebhookDelivery(org_id=org_id, subscription_id=uuid.UUID(sub["id"]), event_type="customer.created", payload={"i": i}, status="success"))
    db_session.commit()
    url = f"/api/webhooks/{sub['id']}/deliveries"
    _assert_clean_paging(client, auth_headers, url, 7, page_size=3)
    assert client.get(url, headers=other_headers).status_code == 404


def test_webhook_deliveries_without_page_keeps_latest_50(client, auth_headers, db_session, org_id):
    sub = client.post("/api/webhooks", json={"target_url": "https://example.com/hook", "event_types": ["customer.created"]}, headers=auth_headers).json()
    for i in range(55):
        db_session.add(WebhookDelivery(org_id=org_id, subscription_id=uuid.UUID(sub["id"]), event_type="customer.created", payload={}, status="success"))
    db_session.commit()
    resp = client.get(f"/api/webhooks/{sub['id']}/deliveries", headers=auth_headers)
    assert len(resp.json()) == 50  # old behaviour preserved...
    assert resp.headers[TOTAL] == "55"  # ...but the header tells the truth


# --- templates ----------------------------------------------------------------


def test_templates_paging_and_search(client, auth_headers, other_headers):
    for name, subject in [("Welcome", "Hi there"), ("Win-back", "We miss you"), ("Promo A", "Sale"), ("Promo B", "Sale 2"), ("Receipt", "Thanks")]:
        client.post("/api/messages/templates", json={"name": name, "subject": subject, "body_html": "<p>x</p>"}, headers=auth_headers)
    _assert_clean_paging(client, auth_headers, "/api/messages/templates", 5)
    assert client.get("/api/messages/templates", params={"search": "promo"}, headers=auth_headers).headers[TOTAL] == "2"  # name
    assert client.get("/api/messages/templates", params={"search": "miss you"}, headers=auth_headers).headers[TOTAL] == "1"  # subject
    assert client.get("/api/messages/templates", headers=other_headers).json() == []


# --- message history ------------------------------------------------------------


def _seed_history(db_session, org_id):
    ada = Customer(org_id=org_id, name="Ada Obi", display_id="CR901")
    bayo = Customer(org_id=org_id, name="Bayo Ade", display_id="CR902")
    db_session.add_all([ada, bayo])
    db_session.flush()
    rows = [
        OutboundMessage(org_id=org_id, customer_id=ada.id, channel=MessageChannel.email, status=MessageStatus.sent, subject="Sale today", body="<p>Hello <b>Ada</b>,</p><p>big sale</p>"),
        OutboundMessage(org_id=org_id, customer_id=ada.id, channel=MessageChannel.email, status=MessageStatus.failed, subject="Sale today", body="<p>x</p>", error="bounced"),
        OutboundMessage(org_id=org_id, customer_id=bayo.id, channel=MessageChannel.whatsapp, status=MessageStatus.sent, subject=None, body="Hi Bayo, restock"),
        OutboundMessage(org_id=org_id, customer_id=bayo.id, channel=MessageChannel.email, status=MessageStatus.skipped, subject="Other", body="<p>y</p>"),
        OutboundMessage(org_id=org_id, customer_id=bayo.id, channel=MessageChannel.email, status=MessageStatus.sent, subject="Thanks", body="z" * 400),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return ada, bayo, rows


def test_history_paging_filters_and_search(client, auth_headers, other_headers, db_session, org_id):
    ada, bayo, _ = _seed_history(db_session, org_id)
    url = "/api/messages/history"
    _assert_clean_paging(client, auth_headers, url, 5)
    assert client.get(url, params={"channel": "whatsapp"}, headers=auth_headers).headers[TOTAL] == "1"
    assert client.get(url, params={"status": "failed"}, headers=auth_headers).headers[TOTAL] == "1"
    assert client.get(url, params={"customer_id": ada.id.hex}, headers=auth_headers).headers[TOTAL] == "2"
    assert client.get(url, params={"search": "restock"}, headers=auth_headers).headers[TOTAL] == "1"  # body
    assert client.get(url, params={"search": "sale today"}, headers=auth_headers).headers[TOTAL] == "2"  # subject
    assert client.get(url, params={"search": "bayo"}, headers=auth_headers).headers[TOTAL] == "3"  # customer name
    _assert_clean_paging(client, auth_headers, url, 3, search="bayo", page_size=2)
    assert client.get(url, params={"channel": "bogus"}, headers=auth_headers).status_code == 422
    assert client.get(url, headers=other_headers).json() == []


def test_history_without_page_still_honours_limit(client, auth_headers, db_session, org_id):
    _seed_history(db_session, org_id)
    resp = client.get("/api/messages/history", params={"limit": 2}, headers=auth_headers)
    assert len(resp.json()) == 2
    assert resp.headers[TOTAL] == "5"


def test_history_rows_have_name_and_preview_but_no_body(client, auth_headers, db_session, org_id):
    _seed_history(db_session, org_id)
    rows = client.get("/api/messages/history", headers=auth_headers).json()
    assert all("body" not in r for r in rows)
    assert {r["customer_name"] for r in rows} == {"Ada Obi", "Bayo Ade"}
    by_subject = {r["subject"]: r for r in rows if r["subject"]}
    assert by_subject["Thanks"]["body_preview"].endswith("…")
    assert len(by_subject["Thanks"]["body_preview"]) <= 160
    html_row = next(r for r in rows if r["body_preview"].startswith("Hello"))
    assert html_row["body_preview"] == "Hello Ada , big sale"  # tags stripped, whitespace collapsed


def test_history_detail_has_full_body_and_is_org_scoped(client, auth_headers, other_headers, db_session, org_id):
    _, _, seeded = _seed_history(db_session, org_id)
    long_one = seeded[4]
    detail = client.get(f"/api/messages/history/{long_one.id}", headers=auth_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["body"] == "z" * 400
    assert body["customer_name"] == "Bayo Ade"
    assert body["channel"] == "email" and body["status"] == "sent"
    assert len(body["body_preview"]) <= 160
    assert client.get(f"/api/messages/history/{long_one.id}", headers=other_headers).status_code == 404
    assert client.get("/api/messages/history/00000000-0000-0000-0000-000000000000", headers=auth_headers).status_code == 404


# --- shared behaviour -------------------------------------------------------------


def test_page_size_is_clamped(client, auth_headers):
    for i in range(3):
        client.post("/api/notes", json={"title": f"n{i}", "content": "c"}, headers=auth_headers)
    assert len(client.get("/api/notes", params={"page": 1, "page_size": 0}, headers=auth_headers).json()) == 1
    assert len(client.get("/api/notes", params={"page": 1, "page_size": 9999}, headers=auth_headers).json()) == 3
    assert len(client.get("/api/notes", params={"page": -4, "page_size": 2}, headers=auth_headers).json()) == 2


def test_total_header_is_exposed_to_browsers():
    from app.main import app

    cors = next(m for m in app.user_middleware if m.cls.__name__ == "CORSMiddleware")
    assert "X-Total-Count" in cors.kwargs["expose_headers"]
