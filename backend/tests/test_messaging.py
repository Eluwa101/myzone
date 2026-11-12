from app.controllers import messaging_controller


class _ImmediateThread:
    """Same pattern as test_webhooks.py / test_notifications.py - runs the
    batch-send synchronously so tests can assert on its outcome instead of
    racing a real background thread."""

    def __init__(self, target=None, args=(), daemon=None):
        self._target = target
        self._args = args

    def start(self):
        self._target(*self._args)


def _create_customer(client, auth_headers, first_name="Ada", last_name="Obi", email="ada@customer.com", consent=True):
    payload = {"first_name": first_name, "last_name": last_name, "email": email}
    if consent:
        payload["consent_date"] = "2026-01-01"
    return client.post("/api/customers", json=payload, headers=auth_headers).json()


def test_list_merge_tags(client, auth_headers):
    resp = client.get("/api/messages/merge-tags", headers=auth_headers)
    assert resp.status_code == 200
    tags = resp.json()
    assert {"category": "customer", "key": "first_name", "tag": "{{customer.first_name}}", "label": "First name", "category_label": "Customer"} in tags
    assert any(t["tag"] == "{{business.name}}" for t in tags)
    assert any(t["tag"] == "{{latest_order.amount}}" for t in tags)


def test_merge_tags_include_this_orgs_custom_fields(client, auth_headers):
    client.post("/api/customers", json={"name": "Ada Obi", "extra": {"Favorite Color": "Blue"}}, headers=auth_headers)

    tags = client.get("/api/messages/merge-tags", headers=auth_headers).json()
    extra_tags = [t for t in tags if t["category"] == "extra"]
    assert extra_tags == [
        {"category": "extra", "category_label": "Custom fields", "key": "favorite_color", "label": "Favorite Color", "tag": "{{extra.favorite_color}}"}
    ]


def test_merge_tags_exclude_other_orgs_custom_fields(client, auth_headers):
    from tests.conftest import verify_user_email

    client.post("/api/auth/signup", json={"org_name": "Other Co", "email": "other3@example.com", "password": "secret123"})
    verify_user_email("other3@example.com")
    other_token = client.post("/api/auth/login", json={"email": "other3@example.com", "password": "secret123"}).json()["access_token"]
    client.post(
        "/api/customers", json={"name": "Bo Chen", "extra": {"Shoe Size": "42"}}, headers={"Authorization": f"Bearer {other_token}"}
    )

    tags = client.get("/api/messages/merge-tags", headers=auth_headers).json()
    assert not any(t["category"] == "extra" for t in tags)


def test_preview_resolves_custom_field_merge_tag(client, auth_headers):
    customer = client.post(
        "/api/customers", json={"name": "Ada Obi", "extra": {"Favorite Color": "Blue"}}, headers=auth_headers
    ).json()

    resp = client.post(
        "/api/messages/preview",
        json={"customer_id": customer["id"], "subject": "x", "body_html": "<p>You love {{extra.favorite_color}}</p>"},
        headers=auth_headers,
    )
    assert "Blue" in resp.json()["body_html"]


def test_create_list_update_delete_template(client, auth_headers):
    created = client.post(
        "/api/messages/templates",
        json={"name": "Welcome", "subject": "Hi {{customer.first_name}}", "body_html": "<p>Welcome, {{customer.first_name}}!</p>"},
        headers=auth_headers,
    )
    assert created.status_code == 201
    template = created.json()

    listed = client.get("/api/messages/templates", headers=auth_headers).json()
    assert len(listed) == 1
    assert listed[0]["name"] == "Welcome"

    updated = client.patch(f"/api/messages/templates/{template['id']}", json={"subject": "Hey there"}, headers=auth_headers)
    assert updated.status_code == 200
    assert updated.json()["subject"] == "Hey there"

    deleted = client.delete(f"/api/messages/templates/{template['id']}", headers=auth_headers)
    assert deleted.status_code == 204
    assert client.get("/api/messages/templates", headers=auth_headers).json() == []


def test_update_unknown_template_404s(client, auth_headers):
    resp = client.patch(
        "/api/messages/templates/00000000-0000-0000-0000-000000000000", json={"name": "x"}, headers=auth_headers
    )
    assert resp.status_code == 404


def test_preview_resolves_merge_tags(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    resp = client.post(
        "/api/messages/preview",
        json={"customer_id": customer["id"], "subject": "Hi {{customer.first_name}}", "body_html": "<p>Your id is {{customer.display_id}}</p>"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["subject"] == "Hi Ada"
    assert customer["display_id"] in body["body_html"]


def test_preview_missing_data_shows_placeholder(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    resp = client.post(
        "/api/messages/preview",
        json={"customer_id": customer["id"], "subject": "Order: {{latest_order.amount}}", "body_html": "x"},
        headers=auth_headers,
    )
    assert resp.json()["subject"] == "Order: —"


def test_preview_unknown_customer_404s(client, auth_headers):
    resp = client.post(
        "/api/messages/preview",
        json={"customer_id": "00000000-0000-0000-0000-000000000000", "subject": "x", "body_html": "x"},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_send_email_batch_resolves_tags_and_logs_sent(client, auth_headers, monkeypatch):
    monkeypatch.setattr(messaging_controller.threading, "Thread", _ImmediateThread)
    sent = []
    monkeypatch.setattr(
        messaging_controller,
        "send_raw",
        lambda to, subject, html, **kw: sent.append((to, subject, html)) or "msg_123",
    )

    customer = _create_customer(client, auth_headers, email="ada@customer.com")

    resp = client.post(
        "/api/messages/send",
        json={"customer_ids": [customer["id"]], "subject": "Hi {{customer.first_name}}", "body_html": "<p>Hello!</p>"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"queued": 1, "skipped_no_email": 0, "skipped_no_consent": 0, "skipped_unsubscribed": 0}
    assert len(sent) == 1
    to, subject, html = sent[0]
    assert (to, subject) == ("ada@customer.com", "Hi Ada")
    assert html.startswith("<p>Hello!</p>") and ">Unsubscribe</a>" in html

    history = client.get("/api/messages/history", headers=auth_headers).json()
    assert len(history) == 1
    assert history[0]["status"] == "sent"
    assert history[0]["subject"] == "Hi Ada"

    notifications = client.get("/api/notifications", headers=auth_headers).json()
    assert any(n["type"] == "message.email.sent" for n in notifications)


def test_send_uses_orgs_own_address_and_falls_back_to_owner_reply_to(client, auth_headers, monkeypatch):
    monkeypatch.setattr(messaging_controller.threading, "Thread", _ImmediateThread)
    captured = {}
    monkeypatch.setattr(messaging_controller, "send_raw", lambda to, subject, html, **kw: captured.update(kw) or "msg_1")
    customer = _create_customer(client, auth_headers)

    client.post(
        "/api/messages/send",
        json={"customer_ids": [customer["id"]], "subject": "Hi", "body_html": "<p>x</p>"},
        headers=auth_headers,
    )
    # the auth_headers org is "Ada's Store", owned by ada@example.com, with
    # no support email set - so replies fall back to the owner
    assert captured["from_address"] == "adasstore@resend.dev"
    assert captured["from_name"] == "Ada's Store"
    assert captured["reply_to"] == "ada@example.com"


def test_send_prefers_support_email_for_reply_to(client, auth_headers, monkeypatch):
    monkeypatch.setattr(messaging_controller.threading, "Thread", _ImmediateThread)
    captured = {}
    monkeypatch.setattr(messaging_controller, "send_raw", lambda to, subject, html, **kw: captured.update(kw) or "msg_1")
    client.put("/api/settings", json={"support_email": "hello@adas.com", "sender_handle": "adaboutique"}, headers=auth_headers)
    customer = _create_customer(client, auth_headers)

    client.post(
        "/api/messages/send",
        json={"customer_ids": [customer["id"]], "subject": "Hi", "body_html": "<p>x</p>"},
        headers=auth_headers,
    )
    assert captured["from_address"] == "adaboutique@resend.dev"
    assert captured["reply_to"] == "hello@adas.com"


def test_send_email_batch_skips_customer_without_email(client, auth_headers, monkeypatch):
    monkeypatch.setattr(messaging_controller.threading, "Thread", _ImmediateThread)
    customer = client.post("/api/customers", json={"name": "No Email Customer"}, headers=auth_headers).json()

    resp = client.post(
        "/api/messages/send",
        json={"customer_ids": [customer["id"]], "subject": "Hi", "body_html": "<p>x</p>"},
        headers=auth_headers,
    )
    assert resp.json() == {"queued": 0, "skipped_no_email": 1, "skipped_no_consent": 0, "skipped_unsubscribed": 0}

    history = client.get("/api/messages/history", headers=auth_headers).json()
    assert history[0]["status"] == "skipped"
    assert history[0]["error"] == "No email on file"


def test_send_email_batch_skips_customer_without_consent_by_default(client, auth_headers, monkeypatch):
    monkeypatch.setattr(messaging_controller.threading, "Thread", _ImmediateThread)
    customer = _create_customer(client, auth_headers, email="ada@customer.com", consent=False)

    resp = client.post(
        "/api/messages/send",
        json={"customer_ids": [customer["id"]], "subject": "Hi", "body_html": "<p>x</p>"},
        headers=auth_headers,
    )
    assert resp.json() == {"queued": 0, "skipped_no_email": 0, "skipped_no_consent": 1, "skipped_unsubscribed": 0}


def test_send_email_batch_can_override_consent_check(client, auth_headers, monkeypatch):
    monkeypatch.setattr(messaging_controller.threading, "Thread", _ImmediateThread)
    monkeypatch.setattr(messaging_controller, "send_raw", lambda *a, **k: "msg_1")
    customer = _create_customer(client, auth_headers, email="ada@customer.com", consent=False)

    resp = client.post(
        "/api/messages/send",
        json={"customer_ids": [customer["id"]], "subject": "Hi", "body_html": "<p>x</p>", "skip_without_consent": False},
        headers=auth_headers,
    )
    assert resp.json() == {"queued": 1, "skipped_no_email": 0, "skipped_no_consent": 0, "skipped_unsubscribed": 0}


def test_send_email_batch_records_failure_per_recipient(client, auth_headers, monkeypatch):
    monkeypatch.setattr(messaging_controller.threading, "Thread", _ImmediateThread)

    def _boom(*a, **k):
        raise RuntimeError("Resend rejected the request")

    monkeypatch.setattr(messaging_controller, "send_raw", _boom)
    customer = _create_customer(client, auth_headers, email="ada@customer.com")

    resp = client.post(
        "/api/messages/send",
        json={"customer_ids": [customer["id"]], "subject": "Hi", "body_html": "<p>x</p>"},
        headers=auth_headers,
    )
    assert resp.json()["queued"] == 1

    history = client.get("/api/messages/history", headers=auth_headers).json()
    assert history[0]["status"] == "failed"

    notifications = client.get("/api/notifications", headers=auth_headers).json()
    assert any(n["type"] == "message.email.partial" for n in notifications)


def test_send_with_unknown_template_404s(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    resp = client.post(
        "/api/messages/send",
        json={
            "customer_ids": [customer["id"]],
            "subject": "Hi",
            "body_html": "x",
            "template_id": "00000000-0000-0000-0000-000000000000",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_messages_require_auth(client):
    assert client.get("/api/messages/templates").status_code == 401
    assert client.get("/api/messages/merge-tags").status_code == 401
