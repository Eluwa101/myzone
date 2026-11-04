"""
Route-level tests. Pending/confirm/reject go through real HTTP + DB, no
LLM involved. The chat endpoint is tested by monkeypatching run_chat
directly, since exercising a real model is out of scope for an automated,
no-API-key-required test suite - the agent's actual decision logic has no
branches of our own to test (that's the model's job); what we own and must
verify is that the route wires run_chat's output into the response shape
correctly.
"""
from uuid import UUID

import app.routes.agent as agent_routes
from app.models.pending_action import PendingAction


def _create_customer(client, headers, **kwargs):
    payload = {"name": "Ada Obi"}
    payload.update(kwargs)
    return client.post("/api/customers", json=payload, headers=headers).json()


def test_pending_list_confirm_and_reject_over_http(client, auth_headers, db_session):
    customer = _create_customer(client, auth_headers)

    # simulate what the delete_customer tool would have created
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "ada@example.com").first()
    pending = PendingAction(
        org_id=user.org_id, user_id=user.id, tool_name="delete_customer",
        payload={"customer_id": customer["id"]}, description=f"Delete customer '{customer['name']}'.",
    )
    db_session.add(pending)
    db_session.commit()
    db_session.refresh(pending)

    listed = client.get("/api/agent/pending", headers=auth_headers).json()
    assert len(listed) == 1
    assert listed[0]["tool_name"] == "delete_customer"

    confirm = client.post(f"/api/agent/pending/{pending.id}/confirm", headers=auth_headers)
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "deleted"

    gone = client.get(f"/api/customers/{customer['id']}", headers=auth_headers)
    assert gone.status_code == 404

    assert client.get("/api/agent/pending", headers=auth_headers).json() == []


def test_rejecting_a_pending_action_over_http(client, auth_headers, db_session):
    customer = _create_customer(client, auth_headers)
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "ada@example.com").first()
    pending = PendingAction(
        org_id=user.org_id, user_id=user.id, tool_name="delete_customer",
        payload={"customer_id": customer["id"]}, description="Delete customer 'Ada Obi'.",
    )
    db_session.add(pending)
    db_session.commit()
    db_session.refresh(pending)

    resp = client.post(f"/api/agent/pending/{pending.id}/reject", headers=auth_headers)
    assert resp.status_code == 204

    still_there = client.get(f"/api/customers/{customer['id']}", headers=auth_headers)
    assert still_there.status_code == 200


def test_confirm_unknown_pending_action_is_404(client, auth_headers):
    resp = client.post(f"/api/agent/pending/{UUID(int=0)}/confirm", headers=auth_headers)
    assert resp.status_code == 404


def test_chat_route_surfaces_pending_actions_from_run_chat(client, auth_headers, db_session, monkeypatch):
    customer = _create_customer(client, auth_headers)
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "ada@example.com").first()
    pending = PendingAction(
        org_id=user.org_id, user_id=user.id, tool_name="delete_customer",
        payload={"customer_id": customer["id"]}, description="Delete customer 'Ada Obi'.",
    )
    db_session.add(pending)
    db_session.commit()
    db_session.refresh(pending)

    def fake_run_chat(db, org_id, user_id, message):
        return "I've prepared that deletion - please confirm it.", [pending]

    monkeypatch.setattr(agent_routes, "run_chat", fake_run_chat)

    resp = client.post("/api/agent/chat", json={"message": "delete Ada Obi"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert "confirm" in body["reply"].lower()
    assert len(body["pending_actions"]) == 1
    assert body["pending_actions"][0]["tool_name"] == "delete_customer"
