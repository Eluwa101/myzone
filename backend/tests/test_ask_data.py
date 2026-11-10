"""
build_data_context is pure DB -> string, tested directly (no LLM call).
The /api/agent/ask route is tested by monkeypatching ask_data itself, same
pattern as the chat route tests - we own the wiring, not the model's
judgment.
"""
import app.routes.agent as agent_routes
from app.agent.ask_data import build_data_context


def test_build_data_context_includes_precomputed_totals_and_customer(client, auth_headers, db_session):
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "ada@example.com").first()

    created = client.post("/api/customers", json={"name": "Ada Obi", "interests": "Rice"}, headers=auth_headers).json()
    client.post(
        f"/api/customers/{created['id']}/transactions",
        json={"date": "2026-11-01", "items": [{"item": "Rice", "qty": 2, "amount": 15000}], "currency": "NGN"},
        headers=auth_headers,
    )

    context = build_data_context(db_session, user.org_id)
    assert "TOTALS (precomputed, exact): 1 customers" in context
    assert "All-time sales: NGN 15,000.00" in context
    assert "Ada Obi" in context
    assert "Rice" in context


def test_ask_route_returns_model_answer(client, auth_headers, monkeypatch):
    def fake_ask_data(db, org_id, question):
        assert question == "who should I follow up with?"
        return "Nobody yet - you have no leads."

    monkeypatch.setattr(agent_routes, "ask_data", fake_ask_data)

    resp = client.post("/api/agent/ask", json={"question": "who should I follow up with?"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"answer": "Nobody yet - you have no leads."}
