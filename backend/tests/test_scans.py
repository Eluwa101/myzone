"""Scanning documents into customer records: finding the customer by the ID
on the paper, recording what it says, and refusing when it isn't safe."""
import base64
import datetime

import pytest

from app.agent import document_reader
from app.controllers import scan_controller
from app.controllers.scan_controller import normalize_display_id

PNG = "data:image/png;base64," + base64.b64encode(b"\x89PNG fake image bytes").decode()


def _png(n: int) -> str:
    return "data:image/png;base64," + base64.b64encode(f"\x89PNG image {n}".encode()).decode()


@pytest.fixture
def reader(monkeypatch):
    """Replaces the vision model: whatever the test puts in reader.result is
    what the "AI" read off the photo."""

    class Reader:
        result: dict = {}
        calls: list = []

    def fake(image_data_url, hint=None):
        Reader.calls.append((image_data_url, hint))
        if isinstance(Reader.result, Exception):
            raise Reader.result
        return Reader.result

    monkeypatch.setattr(scan_controller, "read_document", fake)
    Reader.calls = []
    return Reader


def _customer(client, auth_headers, **kw):
    return client.post("/api/customers", json={"first_name": "Ada", "last_name": "Obi", **kw}, headers=auth_headers).json()


def _scan(client, auth_headers, image=PNG, hint=None):
    resp = client.post("/api/scans", json={"image_data_url": image, "hint": hint}, headers=auth_headers)
    assert resp.status_code == 202, resp.text
    return resp.json()


def _full(client, auth_headers, customer_id):
    return client.get(f"/api/customers/{customer_id}", headers=auth_headers).json()


def _notifications(client, auth_headers):
    return client.get("/api/notifications", headers=auth_headers).json()


def test_display_id_normalizing():
    assert normalize_display_id("CR004")[0] == "CR004"
    assert "CR004" in normalize_display_id("cr 4")
    assert "CR004" in normalize_display_id("CR-004")
    assert "CR042" in normalize_display_id("#CR42")
    assert normalize_display_id("hello") == [] and normalize_display_id(None) == []


def test_receipt_is_recorded_on_the_right_customer(client, auth_headers, reader):
    client.put("/api/settings", json={"default_currency": "NGN"}, headers=auth_headers)
    ada = _customer(client, auth_headers)
    reader.result = {
        "customer_id": f"{ada['display_id'][:2]} {int(ada['display_id'][2:])}",  # written as "CR 1"
        "customer_name": "Mrs A. Obi",
        "document_type": "receipt",
        "date": "2026-11-10",
        "transactions": [{"items": [{"item": "Gas Lighter", "qty": 2, "amount": "1,000"}, {"item": "Cooking Gas", "amount": 9500}]}],
        "customer_fields": {"phone": "+2348012345678", "email": None},
        "custom_fields": {"Favourite brand": "Bic"},
        "summary": "Receipt for lighters and gas",
    }
    scan = _scan(client, auth_headers, hint="from yesterday")
    assert scan["status"] == "processing"
    assert reader.calls[0][1] == "from yesterday"

    customer = _full(client, auth_headers, ada["id"])
    assert len(customer["transactions"]) == 1
    tx = customer["transactions"][0]
    assert tx["date"] == "2026-11-10" and tx["currency"] == "NGN" and float(tx["amount"]) == 10500
    assert [i["item"] for i in tx["items"]] == ["Gas Lighter", "Cooking Gas"]
    assert customer["phone"] == "+2348012345678"
    assert customer["extra"] == {"Favourite brand": "Bic"}

    listed = client.get("/api/scans", headers=auth_headers).json()[0]
    assert listed["status"] == "done" and listed["customer_id"] == ada["id"] and listed["display_id"] == ada["display_id"]
    assert any("Recorded a sale on 2026-11-10" in a and "NGN 10,500.00" in a for a in listed["actions"])
    assert any("phone" in a and "Favourite brand" in a for a in listed["actions"])

    note = _notifications(client, auth_headers)[0]
    assert note["type"] == "scan.done"
    assert note["title"].startswith(f"Scanned receipt for Ada Obi ({ada['display_id']})")
    assert note["link"] == f"/customers/{ada['id']}"


def test_orders_and_leftover_text_become_an_order_and_a_note(client, auth_headers, reader):
    ada = _customer(client, auth_headers)
    reader.result = {
        "customer_id": ada["display_id"],
        "document_type": "order",
        "orders": [{"order_date": "2026-11-11", "delivery_date": "2026-11-20", "items": [{"name": "Birthday cake", "qty": 1, "price": 15000}], "amount": 15000, "currency": "NGN"}],
        "notes": "Wants blue icing, deliver after 4pm",
    }
    _scan(client, auth_headers)
    customer = _full(client, auth_headers, ada["id"])
    assert customer["orders"][0]["delivery_date"] == "2026-11-20"
    notes = client.get("/api/notes", headers=auth_headers).json()
    assert notes[0]["title"] == "From a scanned order" and "blue icing" in notes[0]["content"]
    assert [c["id"] for c in notes[0]["customers"]] == [ada["id"]]


def test_existing_profile_details_are_not_overwritten(client, auth_headers, reader):
    ada = _customer(client, auth_headers, phone="0801111111", extra={"Shoe size": "42"})
    reader.result = {
        "customer_id": ada["display_id"],
        "customer_fields": {"phone": "0809999999", "address": "12 Market Rd"},
        "custom_fields": {"shoe size": "44"},
    }
    _scan(client, auth_headers)
    customer = _full(client, auth_headers, ada["id"])
    assert customer["phone"] == "0801111111" and customer["address"] == "12 Market Rd"
    assert customer["extra"] == {"Shoe size": "42"}
    note = client.get("/api/notes", headers=auth_headers).json()[0]
    assert "0809999999" in note["content"] and "44" in note["content"]


@pytest.mark.parametrize(
    "extracted, title_part",
    [
        ({"customer_id": None, "transactions": [{"items": [{"item": "x", "amount": 5}]}]}, "no customer ID"),
        ({"customer_id": "CR999", "transactions": [{"items": [{"item": "x", "amount": 5}]}]}, "No customer CR999"),
        ({"customer_id": "{id}", "customer_name": "Musa Bello", "transactions": [{"items": [{"item": "x", "amount": 5}]}]}, "doesn't match"),
    ],
)
def test_unsafe_scans_record_nothing(client, auth_headers, reader, extracted, title_part):
    ada = _customer(client, auth_headers)
    reader.result = {k: (v.replace("{id}", ada["display_id"]) if isinstance(v, str) else v) for k, v in extracted.items()}
    _scan(client, auth_headers)
    assert _full(client, auth_headers, ada["id"])["transactions"] == []
    assert client.get("/api/scans", headers=auth_headers).json()[0]["status"] == "needs_review"
    note = _notifications(client, auth_headers)[0]
    assert note["type"] == "scan.needs_review" and title_part in note["title"]


def test_same_photo_twice_is_processed_once(client, auth_headers, reader):
    ada = _customer(client, auth_headers)
    reader.result = {"customer_id": ada["display_id"], "transactions": [{"date": "2026-11-01", "items": [{"item": "Rice", "amount": 500}]}]}
    first = _scan(client, auth_headers)
    second = _scan(client, auth_headers)
    assert first["id"] == second["id"] and len(reader.calls) == 1
    assert len(_full(client, auth_headers, ada["id"])["transactions"]) == 1


def test_a_sale_already_on_record_is_skipped(client, auth_headers, reader):
    ada = _customer(client, auth_headers)
    client.post(f"/api/customers/{ada['id']}/transactions", json={"date": "2026-11-01", "items": [{"item": "Rice", "amount": 500}]}, headers=auth_headers)
    reader.result = {"customer_id": ada["display_id"], "transactions": [{"date": "2026-11-01", "items": [{"item": "rice", "amount": 500}]}]}
    _scan(client, auth_headers, image=_png(2))  # a different photo of the same receipt
    assert len(_full(client, auth_headers, ada["id"])["transactions"]) == 1
    scan = client.get("/api/scans", headers=auth_headers).json()[0]
    assert scan["status"] == "done" and "already recorded" in scan["actions"][0]


def test_unreadable_lines_are_dropped_not_guessed(client, auth_headers, reader):
    ada = _customer(client, auth_headers)
    reader.result = {
        "customer_id": ada["display_id"],
        "transactions": [{"date": "not a date", "items": [{"item": "Rice", "amount": "??"}, {"item": "Oil", "amount": 300}, "junk"]}],
        "customer_fields": {"birthday": "sometime in May"},
    }
    _scan(client, auth_headers)
    customer = _full(client, auth_headers, ada["id"])
    assert [i["item"] for i in customer["transactions"][0]["items"]] == ["Oil"]
    assert customer["transactions"][0]["date"] == datetime.date.today().isoformat()
    assert customer["birthday"] is None


def test_a_failed_read_is_reported_and_can_be_retried(client, auth_headers, reader):
    reader.result = document_reader.DocumentReadError("blurry")
    _scan(client, auth_headers)
    assert client.get("/api/scans", headers=auth_headers).json()[0]["status"] == "failed"
    assert _notifications(client, auth_headers)[0]["type"] == "scan.failed"

    ada = _customer(client, auth_headers)
    reader.result = {"customer_id": ada["display_id"], "transactions": [{"items": [{"item": "Rice", "amount": 5}]}]}
    _scan(client, auth_headers)  # same photo - a failed scan doesn't block retrying it
    assert len(_full(client, auth_headers, ada["id"])["transactions"]) == 1


def test_only_this_business_customers_can_be_matched(client, auth_headers, reader):
    from tests.conftest import verify_user_email

    ada = _customer(client, auth_headers)
    client.post("/api/auth/signup", json={"org_name": "Other", "email": "o@example.com", "password": "secret123"})
    verify_user_email("o@example.com")
    token = client.post("/api/auth/login", json={"email": "o@example.com", "password": "secret123"}).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}

    reader.result = {"customer_id": ada["display_id"], "transactions": [{"items": [{"item": "Rice", "amount": 5}]}]}
    _scan(client, other)  # the other business has no customers, so no CR001
    assert _full(client, auth_headers, ada["id"])["transactions"] == []
    assert client.get("/api/scans", headers=auth_headers).json() == []


@pytest.mark.parametrize("bad", ["not a data url", "data:text/plain;base64,aGVsbG8gd29ybGQgaGVsbG8=", "data:image/png;base64,"])
def test_bad_images_are_rejected(client, auth_headers, bad):
    resp = client.post("/api/scans", json={"image_data_url": bad.ljust(20, "=")}, headers=auth_headers)
    assert resp.status_code == 422


def test_scans_require_auth(client):
    assert client.get("/api/scans").status_code == 401


def test_document_reader_parses_fenced_json(monkeypatch):
    class _Result:
        content = '```json\n{"customer_id": "CR001", "summary": "x"}\n```'

    monkeypatch.setattr(document_reader, "call_vision_with_fallback", lambda invoke: _Result())
    assert document_reader.read_document(PNG)["customer_id"] == "CR001"

    class _Bad:
        content = "I can't read this image."

    monkeypatch.setattr(document_reader, "call_vision_with_fallback", lambda invoke: _Bad())
    with pytest.raises(document_reader.DocumentReadError):
        document_reader.read_document(PNG)
