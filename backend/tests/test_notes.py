import pytest

from app.agent.tools import build_tools


def _create_customer(client, auth_headers, name="Ada Obi"):
    return client.post("/api/customers", json={"name": name}, headers=auth_headers).json()


def test_create_note_attached_to_multiple_customers(client, auth_headers):
    a = _create_customer(client, auth_headers, "Ada Obi")
    b = _create_customer(client, auth_headers, "Bola Ade")

    resp = client.post(
        "/api/notes",
        json={"title": "Creditors", "content": "Owes for last month's delivery", "customer_ids": [a["id"], b["id"]]},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["is_pending_review"] is False
    assert {c["id"] for c in body["customers"]} == {a["id"], b["id"]}


def test_list_notes_filtered_by_customer(client, auth_headers):
    a = _create_customer(client, auth_headers, "Ada Obi")
    b = _create_customer(client, auth_headers, "Bola Ade")
    client.post("/api/notes", json={"title": "VIP", "content": "Top spender", "customer_ids": [a["id"]]}, headers=auth_headers)
    client.post("/api/notes", json={"title": "Other", "content": "Unrelated", "customer_ids": [b["id"]]}, headers=auth_headers)

    resp = client.get("/api/notes", params={"customer_id": a["id"]}, headers=auth_headers)
    assert resp.status_code == 200
    titles = [n["title"] for n in resp.json()]
    assert titles == ["VIP"]


def test_pending_count_and_mark_reviewed(client, auth_headers):
    a = _create_customer(client, auth_headers, "Ada Obi")
    created = client.post(
        "/api/notes",
        json={"title": "Ambiguous info", "content": "Something unclear", "customer_ids": [a["id"]]},
        headers=auth_headers,
    ).json()
    assert created["is_pending_review"] is False  # direct API create defaults to not-pending

    client.patch(f"/api/notes/{created['id']}", json={"is_pending_review": True}, headers=auth_headers)
    count = client.get("/api/notes/pending/count", headers=auth_headers).json()
    assert count["count"] == 1

    client.patch(f"/api/notes/{created['id']}", json={"is_pending_review": False}, headers=auth_headers)
    count_after = client.get("/api/notes/pending/count", headers=auth_headers).json()
    assert count_after["count"] == 0


def test_delete_note(client, auth_headers):
    created = client.post("/api/notes", json={"title": "Temp", "content": "x"}, headers=auth_headers).json()
    resp = client.delete(f"/api/notes/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204
    assert client.get("/api/notes", headers=auth_headers).json() == []


@pytest.fixture
def tools(db_session, seeded_org):
    org_id, user_id = seeded_org
    return {t.name: t for t in build_tools(db_session, org_id, user_id)}


def test_agent_set_custom_field_tool(db_session, seeded_org, tools):
    from app.controllers import customer_controller
    from app.schemas.customer import CustomerCreate

    org_id, _ = seeded_org
    customer = customer_controller.create_customer(db_session, org_id, CustomerCreate(name="Ada Obi"))

    result = tools["set_customer_custom_field"].invoke({"customer_id": str(customer.id), "field_name": "Car", "value": "Toyota Camry"})
    assert result["action"] == "field_set"
    assert result["extra"]["Car"] == "Toyota Camry"


def test_agent_add_customer_note_tool_creates_pending_note(db_session, seeded_org, tools):
    from app.controllers import customer_controller, note_controller
    from app.schemas.customer import CustomerCreate

    org_id, _ = seeded_org
    customer = customer_controller.create_customer(db_session, org_id, CustomerCreate(name="Ada Obi"))

    result = tools["add_customer_note"].invoke({"customer_id": str(customer.id), "title": "Heads up", "content": "Mentioned moving soon"})
    assert result["status"] == "pending_review"
    assert result["is_pending_review"] is True
    assert result["created_by_agent"] is True

    assert note_controller.count_pending(db_session, org_id) == 1
