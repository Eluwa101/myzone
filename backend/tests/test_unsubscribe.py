"""Unsubscribe links: the footer and headers on every customer email, the
public endpoints behind them, and skipping people who opted out."""
from app.controllers import messaging_controller
from app.core import unsubscribe
from app.core.config import settings


class _ImmediateThread:
    def __init__(self, target=None, args=(), daemon=None):
        self._target, self._args = target, args

    def start(self):
        self._target(*self._args)


def _customer(client, auth_headers, email="ada@customer.com"):
    return client.post(
        "/api/customers", json={"first_name": "Ada", "last_name": "Obi", "email": email, "consent_date": "2026-01-01"}, headers=auth_headers
    ).json()


def _capture_sends(monkeypatch):
    sent = []
    monkeypatch.setattr(messaging_controller.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(messaging_controller, "send_raw", lambda to, subject, html, **kw: sent.append({"to": to, "html": html, **kw}) or "id")
    return sent


def _send(client, auth_headers, ids, **extra):
    return client.post("/api/messages/send", json={"customer_ids": ids, "subject": "Hi", "body_html": "<p>Hello</p>", **extra}, headers=auth_headers).json()


def test_token_round_trip_and_tamper_proof(client, auth_headers):
    customer = _customer(client, auth_headers)
    from uuid import UUID

    token = unsubscribe.make_token(UUID(customer["id"]))
    assert unsubscribe.read_token(token) == UUID(customer["id"])
    other = "0" * 32
    assert unsubscribe.read_token(other + token[32:]) is None  # someone else's id with this signature
    assert unsubscribe.read_token(token[:-1] + ("A" if token[-1] != "A" else "B")) is None
    assert unsubscribe.read_token("garbage") is None


def test_every_email_gets_a_footer_link_and_list_unsubscribe_headers(client, auth_headers, monkeypatch):
    sent = _capture_sends(monkeypatch)
    customer = _customer(client, auth_headers)
    monkeypatch.setattr(settings, "api_public_url", "https://api.example.com")
    _send(client, auth_headers, [customer["id"]])

    mail = sent[0]
    token = unsubscribe.make_token(__import__("uuid").UUID(customer["id"]))
    assert f"/unsubscribe/{token}" in mail["html"] and "customer of Ada&#x27;s Store" in mail["html"]
    assert mail["headers"] == {
        "List-Unsubscribe": f"<https://api.example.com/api/public/unsubscribe/{token}>",
        "List-Unsubscribe-Post": "List-Unsubscribe=One-Click",
    }


def test_without_api_url_the_header_points_at_the_page(client, auth_headers, monkeypatch):
    sent = _capture_sends(monkeypatch)
    monkeypatch.setattr(settings, "api_public_url", None)
    customer = _customer(client, auth_headers)
    _send(client, auth_headers, [customer["id"]])
    assert sent[0]["headers"]["List-Unsubscribe"].startswith(f"<{settings.frontend_url}/unsubscribe/")
    assert "List-Unsubscribe-Post" not in sent[0]["headers"]


def test_footer_goes_inside_a_full_html_document(client, auth_headers, monkeypatch):
    sent = _capture_sends(monkeypatch)
    customer = _customer(client, auth_headers)
    _send(client, auth_headers, [customer["id"]], body_html="<html><body><table><tr><td>Hi</td></tr></table></body></html>")
    html = sent[0]["html"]
    assert html.index("Unsubscribe") < html.index("</body>")


def test_unsubscribe_flow_skips_future_sends_and_notifies(client, auth_headers, monkeypatch):
    sent = _capture_sends(monkeypatch)
    customer = _customer(client, auth_headers)
    other = _customer(client, auth_headers, email="bo@customer.com")
    token = unsubscribe.make_token(__import__("uuid").UUID(customer["id"]))

    status = client.get(f"/api/public/unsubscribe/{token}").json()
    assert status == {"business_name": "Ada's Store", "unsubscribed": False}

    # a mail app's one-click POST, form-encoded, no auth - and safe to repeat
    for _ in range(2):
        resp = client.post(f"/api/public/unsubscribe/{token}", content="List-Unsubscribe=One-Click", headers={"Content-Type": "application/x-www-form-urlencoded"})
        assert resp.status_code == 200 and resp.json()["unsubscribed"] is True

    detail = client.get(f"/api/customers/{customer['id']}", headers=auth_headers).json()
    assert detail["email_unsubscribed_at"] is not None
    notifications = client.get("/api/notifications", headers=auth_headers).json()
    assert sum(n["type"] == "customer.unsubscribed" for n in notifications) == 1

    # even with the consent check switched off, an unsubscribed customer is skipped
    result = _send(client, auth_headers, [customer["id"], other["id"]], skip_without_consent=False)
    assert result == {"queued": 1, "skipped_no_email": 0, "skipped_no_consent": 0, "skipped_unsubscribed": 1}
    assert [m["to"] for m in sent] == ["bo@customer.com"]
    history = client.get("/api/messages/history", headers=auth_headers).json()
    assert any(h["status"] == "skipped" and h["error"] == "Unsubscribed" for h in history)


def test_customer_can_resubscribe(client, auth_headers, monkeypatch):
    sent = _capture_sends(monkeypatch)
    customer = _customer(client, auth_headers)
    token = unsubscribe.make_token(__import__("uuid").UUID(customer["id"]))
    client.post(f"/api/public/unsubscribe/{token}")
    assert client.post(f"/api/public/unsubscribe/{token}/resubscribe").json()["unsubscribed"] is False
    assert _send(client, auth_headers, [customer["id"]])["queued"] == 1
    assert len(sent) == 1


def test_business_cannot_clear_an_unsubscribe(client, auth_headers):
    customer = _customer(client, auth_headers)
    token = unsubscribe.make_token(__import__("uuid").UUID(customer["id"]))
    client.post(f"/api/public/unsubscribe/{token}")
    client.patch(f"/api/customers/{customer['id']}", json={"email_unsubscribed_at": None, "name": "Ada O"}, headers=auth_headers)
    assert client.get(f"/api/customers/{customer['id']}", headers=auth_headers).json()["email_unsubscribed_at"] is not None


def test_bad_tokens_404(client):
    assert client.get("/api/public/unsubscribe/nope").status_code == 404
    assert client.post(f"/api/public/unsubscribe/{'a' * 32}.forgedsignature1234567").status_code == 404


def test_sql_segments_can_exclude_unsubscribed(client, auth_headers):
    customer = _customer(client, auth_headers)
    _customer(client, auth_headers, email="bo@customer.com")
    client.post(f"/api/public/unsubscribe/{unsubscribe.make_token(__import__('uuid').UUID(customer['id']))}")
    resp = client.post("/api/segments/sql/preview", json={"sql": "SELECT id FROM customers WHERE email_unsubscribed = 0"}, headers=auth_headers)
    assert resp.json()["total"] == 1
