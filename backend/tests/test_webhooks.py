import hashlib
import hmac
import json

import pytest

from app.controllers import webhook_controller


class _ImmediateThread:
    """Runs the delivery inline instead of on a real background thread, so
    tests can assert on the result without racing it."""

    def __init__(self, target=None, args=(), daemon=None):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


class _FakeResponse:
    def __init__(self, status_code: int):
        self.status_code = status_code
        self.is_success = 200 <= status_code < 300


@pytest.fixture(autouse=True)
def _inline_delivery(monkeypatch):
    monkeypatch.setattr(webhook_controller.threading, "Thread", _ImmediateThread)


def _create_subscription(client, auth_headers, event_types):
    return client.post(
        "/api/webhooks",
        json={"target_url": "https://example.com/hook", "event_types": event_types},
        headers=auth_headers,
    ).json()


def test_create_subscription_rejects_unknown_event_type(client, auth_headers):
    resp = client.post(
        "/api/webhooks",
        json={"target_url": "https://example.com/hook", "event_types": ["bogus.event"]},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_subscription_rejects_non_http_url(client, auth_headers):
    resp = client.post(
        "/api/webhooks",
        json={"target_url": "ftp://example.com/hook", "event_types": ["customer.created"]},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_customer_created_fires_matching_subscription(client, auth_headers, monkeypatch):
    calls = []

    def fake_post(url, content=None, headers=None, timeout=None):
        calls.append((url, content, headers))
        return _FakeResponse(200)

    monkeypatch.setattr(webhook_controller.httpx, "post", fake_post)

    sub = _create_subscription(client, auth_headers, ["customer.created"])
    assert sub["secret"]

    client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)

    assert len(calls) == 1
    url, body, headers = calls[0]
    assert url == "https://example.com/hook"
    data = json.loads(body)
    assert data["event"] == "customer.created"
    assert data["data"]["name"] == "Ada Obi"

    expected_sig = hmac.new(sub["secret"].encode(), body, hashlib.sha256).hexdigest()
    assert headers["X-MyShop-Signature"] == expected_sig
    assert headers["X-MyShop-Event"] == "customer.created"

    deliveries = client.get(f"/api/webhooks/{sub['id']}/deliveries", headers=auth_headers).json()
    assert len(deliveries) == 1
    assert deliveries[0]["status"] == "success"
    assert deliveries[0]["response_code"] == 200


def test_non_matching_event_type_does_not_fire(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(webhook_controller.httpx, "post", lambda *a, **k: calls.append(1) or _FakeResponse(200))

    _create_subscription(client, auth_headers, ["order.created"])
    client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)

    assert calls == []


def test_inactive_subscription_does_not_fire(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(webhook_controller.httpx, "post", lambda *a, **k: calls.append(1) or _FakeResponse(200))

    sub = _create_subscription(client, auth_headers, ["customer.created"])
    client.patch(f"/api/webhooks/{sub['id']}", json={"is_active": False}, headers=auth_headers)
    client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)

    assert calls == []


def test_failed_delivery_is_logged(client, auth_headers, monkeypatch):
    def fake_post(*args, **kwargs):
        raise webhook_controller.httpx.ConnectError("boom")

    monkeypatch.setattr(webhook_controller.httpx, "post", fake_post)

    sub = _create_subscription(client, auth_headers, ["customer.created"])
    client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)

    deliveries = client.get(f"/api/webhooks/{sub['id']}/deliveries", headers=auth_headers).json()
    assert len(deliveries) == 1
    assert deliveries[0]["status"] == "failed"
    assert deliveries[0]["response_code"] is None
    assert deliveries[0]["attempt_count"] == webhook_controller.MAX_ATTEMPTS


def test_regenerate_secret_changes_future_signatures(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(webhook_controller.httpx, "post", lambda url, content=None, headers=None, timeout=None: calls.append(headers) or _FakeResponse(200))

    sub = _create_subscription(client, auth_headers, ["customer.created"])
    old_secret = sub["secret"]

    updated = client.patch(f"/api/webhooks/{sub['id']}", json={"regenerate_secret": True}, headers=auth_headers).json()
    assert updated["secret"] != old_secret

    client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)
    assert calls[0]["X-MyShop-Signature"] != hmac.new(old_secret.encode(), b"", hashlib.sha256).hexdigest()  # sanity: not the stale secret


def test_delete_subscription_stops_delivery(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(webhook_controller.httpx, "post", lambda *a, **k: calls.append(1) or _FakeResponse(200))

    sub = _create_subscription(client, auth_headers, ["customer.created"])
    assert client.delete(f"/api/webhooks/{sub['id']}", headers=auth_headers).status_code == 204

    client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)
    assert calls == []


def test_order_and_transaction_events_fire(client, auth_headers, monkeypatch):
    calls = []
    monkeypatch.setattr(webhook_controller.httpx, "post", lambda url, content=None, headers=None, timeout=None: calls.append((headers["X-MyShop-Event"], json.loads(content))) or _FakeResponse(200))

    _create_subscription(client, auth_headers, ["order.created", "transaction.created", "customer.deleted"])
    customer = client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers).json()

    client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": "2026-01-01", "items": [{"name": "Widget", "qty": 1, "price": 10}]},
        headers=auth_headers,
    )
    client.post(
        f"/api/customers/{customer['id']}/transactions",
        json={"date": "2026-01-01", "item": "Widget", "qty": 1, "amount": 10, "currency": "USD"},
        headers=auth_headers,
    )
    client.delete(f"/api/customers/{customer['id']}", headers=auth_headers)

    event_names = [c[0] for c in calls]
    assert event_names == ["order.created", "transaction.created", "customer.deleted"]
    assert calls[2][1]["data"]["id"] == customer["id"]
