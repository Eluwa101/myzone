"""
The customer activity timeline: what is derived from existing tables, what is
recorded in customer_events, and that merges keep history whole.
"""
from datetime import date, timedelta
from uuid import UUID

from tests.conftest import verify_user_email


def _customer(client, headers, **fields):
    return client.post("/api/customers", json={"name": "Ada Obi", **fields}, headers=headers).json()


def _activity(client, headers, customer_id, **params):
    resp = client.get(f"/api/customers/{customer_id}/activity", params=params, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _titles(data):
    return [i["title"] for i in data["items"]]


def _kinds(data):
    return [i["kind"] for i in data["items"]]


def test_new_customer_timeline_starts_with_creation(client, auth_headers):
    c = _customer(client, auth_headers)
    data = _activity(client, auth_headers, c["id"])
    assert data["total"] == 1
    assert data["items"][0]["kind"] == "customer_created"
    assert c["display_id"] in data["items"][0]["detail"]


def test_timeline_unions_orders_purchases_notes_and_emails_newest_first(client, auth_headers, db_session):
    from app.models.outbound_message import MessageChannel, MessageStatus, OutboundMessage
    from app.models.user import User

    org_id = db_session.query(User).filter(User.email == "ada@example.com").first().org_id
    c = _customer(client, auth_headers, email="ada@mail.com")
    client.post(
        f"/api/customers/{c['id']}/orders",
        json={"order_date": str(date.today()), "items": [{"name": "Generator", "qty": 2}], "amount": 5000, "currency": "NGN"},
        headers=auth_headers,
    )
    client.post(
        f"/api/customers/{c['id']}/transactions",
        json={"date": str(date.today()), "items": [{"item": "Rice", "qty": 1, "amount": 700}], "currency": "NGN"},
        headers=auth_headers,
    )
    client.post("/api/notes", json={"title": "Prefers mornings", "content": "Call before noon", "customer_ids": [c["id"]]}, headers=auth_headers)
    db_session.add_all([
        OutboundMessage(org_id=org_id, customer_id=UUID(c["id"]), channel=MessageChannel.email, status=MessageStatus.sent, subject="Sale", body="<p>hi</p>"),
        OutboundMessage(org_id=org_id, customer_id=UUID(c["id"]), channel=MessageChannel.email, status=MessageStatus.skipped, subject="Sale", body="", error="Unsubscribed"),
    ])
    db_session.commit()

    data = _activity(client, auth_headers, c["id"])
    kinds = _kinds(data)
    for expected in ("customer_created", "order_created", "transaction_added", "note_added", "email"):
        assert expected in kinds, (expected, kinds)
    assert kinds.count("email") == 2
    assert kinds[-1] == "customer_created"  # oldest last
    ats = [i["at"] for i in data["items"]]
    assert ats == sorted(ats, reverse=True)

    skipped = next(i for i in data["items"] if i["status"] == "skipped")
    assert skipped["title"].startswith("Email skipped") and skipped["detail"] == "Unsubscribed"
    order = next(i for i in data["items"] if i["kind"] == "order_created")
    assert "Generator" in order["detail"] and "5,000.00 NGN" in order["detail"]


def test_profile_and_status_changes_are_recorded_with_before_and_after(client, auth_headers):
    c = _customer(client, auth_headers, phone="0801", status="lead")
    client.patch(f"/api/customers/{c['id']}", json={"phone": "0802", "job": "Baker", "extra": {"Car": "Camry"}}, headers=auth_headers)
    client.patch(f"/api/customers/{c['id']}", json={"status": "inactive"}, headers=auth_headers)

    items = _activity(client, auth_headers, c["id"])["items"]
    updates = [i for i in items if i["kind"] == "profile_updated"]
    assert len(updates) == 2
    details = " | ".join(u["detail"] for u in updates)
    assert "phone: 0801 → 0802" in details
    assert "job: (blank) → Baker" in details
    assert "Car: (blank) → Camry" in details
    assert "status:" in details and "inactive" in details


def test_noop_update_records_nothing(client, auth_headers):
    c = _customer(client, auth_headers, phone="0801")
    client.patch(f"/api/customers/{c['id']}", json={"phone": "0801"}, headers=auth_headers)
    assert "profile_updated" not in _kinds(_activity(client, auth_headers, c["id"]))


def test_order_and_transaction_edits_and_deletes_survive_in_history(client, auth_headers):
    c = _customer(client, auth_headers)
    order = client.post(
        f"/api/customers/{c['id']}/orders",
        json={"order_date": str(date.today()), "items": [{"name": "Generator"}]}, headers=auth_headers,
    ).json()
    tx = client.post(
        f"/api/customers/{c['id']}/transactions",
        json={"date": str(date.today()), "items": [{"item": "Rice", "qty": 1, "amount": 700}], "currency": "NGN"}, headers=auth_headers,
    ).json()

    client.patch(f"/api/customers/{c['id']}/orders/{order['id']}", json={"delivered": True, "delivery_date": str(date.today() + timedelta(days=2))}, headers=auth_headers)
    client.patch(f"/api/customers/{c['id']}/transactions/{tx['id']}", json={"items": [{"item": "Rice", "qty": 1, "amount": 900}]}, headers=auth_headers)
    client.delete(f"/api/customers/{c['id']}/orders/{order['id']}", headers=auth_headers)
    client.delete(f"/api/customers/{c['id']}/transactions/{tx['id']}", headers=auth_headers)

    data = _activity(client, auth_headers, c["id"])
    kinds = _kinds(data)
    for expected in ("order_updated", "order_deleted", "transaction_updated", "transaction_deleted"):
        assert expected in kinds, (expected, kinds)
    order_update = next(i for i in data["items"] if i["kind"] == "order_updated")
    assert "marked delivered" in order_update["detail"] and "delivery date" in order_update["detail"]
    tx_update = next(i for i in data["items"] if i["kind"] == "transaction_updated")
    assert "700" in tx_update["detail"] and "900" in tx_update["detail"]
    assert "Generator" in next(i for i in data["items"] if i["kind"] == "order_deleted")["detail"]
    # the creations are gone with the rows (they were derived) - the deletion events are the lasting trace
    assert "order_created" not in kinds and "transaction_added" not in kinds


def test_whatsapp_opened_is_logged_honestly(client, auth_headers):
    c = _customer(client, auth_headers, phone="+2348012345678")
    resp = client.post(f"/api/customers/{c['id']}/activity/whatsapp", json={"message": "Hi Ada,\n\nyour order   is ready"}, headers=auth_headers)
    assert resp.status_code == 204
    item = next(i for i in _activity(client, auth_headers, c["id"])["items"] if i["kind"] == "whatsapp_opened")
    assert item["title"] == "WhatsApp chat opened"  # never claims "sent"
    assert item["status"] == "opened"
    assert item["detail"] == "Hi Ada, your order is ready"


def test_merge_keeps_whole_history_on_the_survivor(client, auth_headers, db_session):
    from app.models.outbound_message import MessageChannel, MessageStatus, OutboundMessage
    from app.models.user import User

    org_id = db_session.query(User).filter(User.email == "ada@example.com").first().org_id
    keep = _customer(client, auth_headers, email="ada@mail.com")
    dupe = client.post("/api/customers?force=true", json={"name": "Ada O.", "phone": "0801", "email": "ada@mail.com"}, headers=auth_headers).json()

    client.post(f"/api/customers/{dupe['id']}/orders", json={"order_date": str(date.today()), "items": [{"name": "Fridge"}]}, headers=auth_headers)
    client.post(f"/api/customers/{dupe['id']}/transactions", json={"date": str(date.today()), "items": [{"item": "Rice", "qty": 1, "amount": 700}], "currency": "NGN"}, headers=auth_headers)
    client.post("/api/notes", json={"title": "Shared", "content": "x", "customer_ids": [dupe["id"]]}, headers=auth_headers)
    client.post(f"/api/customers/{dupe['id']}/activity/whatsapp", json={"message": "hello"}, headers=auth_headers)
    db_session.add(OutboundMessage(org_id=org_id, customer_id=UUID(dupe["id"]), channel=MessageChannel.email, status=MessageStatus.sent, subject="Old mail", body="b"))
    db_session.commit()

    merged = client.post("/api/customers/merge", json={"keep_id": keep["id"], "merge_id": dupe["id"]}, headers=auth_headers)
    assert merged.status_code == 200, merged.text
    assert len(merged.json()["orders"]) == 1 and len(merged.json()["transactions"]) == 1  # nothing lost

    data = _activity(client, auth_headers, keep["id"])
    kinds = _kinds(data)
    for expected in ("merged", "order_created", "transaction_added", "note_added", "email", "whatsapp_opened"):
        assert expected in kinds, (expected, kinds)
    merged_item = next(i for i in data["items"] if i["kind"] == "merged")
    assert "Ada O." in merged_item["title"] and "1 order(s) moved" in merged_item["detail"]

    assert client.get(f"/api/customers/{dupe['id']}/activity", headers=auth_headers).status_code == 404


def test_paging(client, auth_headers):
    c = _customer(client, auth_headers)
    for n in range(4):
        client.patch(f"/api/customers/{c['id']}", json={"job": f"Job {n}"}, headers=auth_headers)
    first = _activity(client, auth_headers, c["id"], page=1, page_size=2)
    second = _activity(client, auth_headers, c["id"], page=2, page_size=2)
    last = _activity(client, auth_headers, c["id"], page=3, page_size=2)
    assert first["total"] == 5 and len(first["items"]) == 2 and len(second["items"]) == 2 and len(last["items"]) == 1
    ids = [i["id"] for p in (first, second, last) for i in p["items"]]
    assert len(set(ids)) == 5


def test_activity_is_org_scoped(client, auth_headers):
    c = _customer(client, auth_headers)
    client.post("/api/auth/signup", json={"org_name": "Other Co", "email": "bola@example.com", "password": "supersecret"})
    verify_user_email("bola@example.com")
    token = client.post("/api/auth/login", json={"email": "bola@example.com", "password": "supersecret"}).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/customers/{c['id']}/activity", headers=other).status_code == 404
    assert client.post(f"/api/customers/{c['id']}/activity/whatsapp", json={"message": "x"}, headers=other).status_code == 404


def test_deleting_a_customer_removes_their_history(client, auth_headers, db_session):
    from app.models.customer_event import CustomerEvent

    c = _customer(client, auth_headers, phone="0801")
    client.patch(f"/api/customers/{c['id']}", json={"phone": "0802"}, headers=auth_headers)
    assert db_session.query(CustomerEvent).count() == 1
    assert client.delete(f"/api/customers/{c['id']}", headers=auth_headers).status_code == 204
    assert db_session.query(CustomerEvent).count() == 0


def test_assistant_read_tool_returns_the_same_history(db_session, seeded_org):
    from app.agent.tools import build_tools

    org_id, user_id = seeded_org
    tools = {t.name: t for t in build_tools(db_session, org_id, user_id)}
    ada = tools["create_customer"].invoke({"name": "Ada Obi", "phone": "0801"})
    tools["update_customer"].invoke({"customer_id": ada["id"], "phone": "0802"})
    out = tools["get_customer_activity"].invoke({"customer_id": ada["id"]})
    assert out["customer"] == "Ada Obi"
    assert [a["kind"] for a in out["activity"]] == ["profile_updated", "customer_created"]
    assert tools["get_customer_activity"].invoke({"customer_id": "nope"})["status"] == "error"
