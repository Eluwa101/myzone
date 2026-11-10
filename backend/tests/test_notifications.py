def _create_customer(client, auth_headers, name="Ada Obi"):
    return client.post("/api/customers", json={"name": name}, headers=auth_headers).json()


def test_creating_an_order_notifies(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": "2026-11-05", "items": [{"name": "Rice"}]},
        headers=auth_headers,
    )

    notifications = client.get("/api/notifications", headers=auth_headers).json()
    order_notes = [n for n in notifications if n["type"] == "order.created"]
    assert len(order_notes) == 1
    assert "Ada Obi" in order_notes[0]["title"]
    assert order_notes[0]["read"] is False
    assert order_notes[0]["link"] == f"/customers/{customer['id']}?tab=orders"


def test_unread_count_and_mark_read(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": "2026-11-05", "items": [{"name": "Rice"}]},
        headers=auth_headers,
    )

    count = client.get("/api/notifications/unread-count", headers=auth_headers).json()
    assert count["count"] == 1

    notification_id = client.get("/api/notifications", headers=auth_headers).json()[0]["id"]
    resp = client.post(f"/api/notifications/{notification_id}/read", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["read"] is True

    count = client.get("/api/notifications/unread-count", headers=auth_headers).json()
    assert count["count"] == 0


def test_mark_all_read(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    for _ in range(3):
        client.post(
            f"/api/customers/{customer['id']}/orders",
            json={"order_date": "2026-11-05", "items": [{"name": "Rice"}]},
            headers=auth_headers,
        )

    resp = client.post("/api/notifications/read-all", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["updated"] == 3
    assert client.get("/api/notifications/unread-count", headers=auth_headers).json()["count"] == 0


def test_mark_read_unknown_notification_404s(client, auth_headers):
    resp = client.post("/api/notifications/00000000-0000-0000-0000-000000000000/read", headers=auth_headers)
    assert resp.status_code == 404


def test_notifications_require_auth(client):
    assert client.get("/api/notifications").status_code == 401


def test_webhook_subscription_creation_notifies(client, auth_headers):
    client.post(
        "/api/webhooks",
        json={"target_url": "https://example.com/hook", "event_types": ["customer.created"]},
        headers=auth_headers,
    )
    notifications = client.get("/api/notifications", headers=auth_headers).json()
    assert any(n["type"] == "webhook.created" for n in notifications)


def test_webhook_delivery_outcome_notifies(client, auth_headers, monkeypatch):
    from app.controllers import webhook_controller

    class _ImmediateThread:
        def __init__(self, target=None, args=(), daemon=None):
            self._target = target
            self._args = args

        def start(self):
            self._target(*self._args)

    monkeypatch.setattr(webhook_controller.threading, "Thread", _ImmediateThread)

    class _FakeResponse:
        def __init__(self, status_code):
            self.status_code = status_code
            self.is_success = 200 <= status_code < 300

    monkeypatch.setattr(webhook_controller.httpx, "post", lambda url, content=None, headers=None, timeout=None: _FakeResponse(200))

    client.post(
        "/api/webhooks",
        json={"target_url": "https://example.com/hook", "event_types": ["customer.created"]},
        headers=auth_headers,
    )
    client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)

    notifications = client.get("/api/notifications", headers=auth_headers).json()
    assert any(n["type"] == "webhook.delivery.success" for n in notifications)


def test_csv_import_notifies(client, auth_headers):
    csv_text = "name,phone\nAda Obi,08011112222\nBola Ade,08033334444\n"
    client.post("/api/customers/import", json={"csv_text": csv_text}, headers=auth_headers)

    notifications = client.get("/api/notifications", headers=auth_headers).json()
    assert any(n["type"] == "import.completed" and "2 added" in n["title"] for n in notifications)


def test_public_form_submission_notifies(client, auth_headers):
    form = client.post(
        "/api/forms",
        json={
            "name": "Contact us",
            "fields": [
                {"key": "first_name", "label": "First name", "type": "text", "required": True, "category": "customer"},
                {"key": "last_name", "label": "Last name", "type": "text", "required": False, "category": "customer"},
                {"key": "phone", "label": "Phone", "type": "tel", "required": False, "category": "customer"},
                {"key": "email", "label": "Email", "type": "email", "required": False, "category": "customer"},
            ],
        },
        headers=auth_headers,
    ).json()

    client.post(f"/api/public/forms/{form['public_token']}/submit", json={"first_name": "Ada", "last_name": "Obi"})

    notifications = client.get("/api/notifications", headers=auth_headers).json()
    assert any(n["type"] == "form.submission" for n in notifications)
