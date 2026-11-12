"""Account closure: requesting it, the read-only period, cancelling, and
the final deletion of everything the business had."""
import datetime
import uuid

from sqlalchemy import func, select

from app.controllers import account_closure_controller as closure
from app.core import email
from app.core.database import Base
from app.models.agent_action import AgentAction
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.document_scan import DocumentScan
from app.models.organization import Organization
from app.models.pending_action import PendingAction
from app.models.saved_widget import SavedWidget
from app.models.user import User, UserRole
from app.models.webhook import WebhookDelivery, WebhookSubscription
from tests.conftest import verify_user_email

FORM_FIELDS = [
    {"key": "first_name", "label": "First name", "type": "text", "required": True, "category": "customer"},
    {"key": "last_name", "label": "Last name", "type": "text", "required": False, "category": "customer"},
    {"key": "phone", "label": "Phone", "type": "tel", "required": False, "category": "customer"},
    {"key": "email", "label": "Email", "type": "email", "required": False, "category": "customer"},
]


def _signup(client, org_name, email_addr):
    client.post("/api/auth/signup", json={"org_name": org_name, "email": email_addr, "password": "secret123"})
    verify_user_email(email_addr)
    token = client.post("/api/auth/login", json={"email": email_addr, "password": "secret123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _capture_emails(monkeypatch):
    sent = []
    monkeypatch.setattr(email, "_send", lambda to, subject, html, **kw: sent.append((to, subject)))
    return sent


def _close(client, headers, name="Ada's Store"):
    return client.post("/api/account/closure", json={"confirm_name": name}, headers=headers)


# --- requesting and cancelling -----------------------------------------------


def test_request_closure_needs_the_exact_business_name(client, auth_headers):
    assert _close(client, auth_headers, "Ada").status_code == 422
    assert client.get("/api/account/closure", headers=auth_headers).json()["closing"] is False

    resp = _close(client, auth_headers, "  ada's   STORE ")  # case and spacing don't matter
    assert resp.status_code == 200
    body = resp.json()
    assert body["closing"] is True and body["requested_by"] == "ada@example.com"
    scheduled = datetime.datetime.fromisoformat(body["scheduled_for"].replace("Z", "+00:00"))
    requested = datetime.datetime.fromisoformat(body["requested_at"].replace("Z", "+00:00"))
    assert scheduled - requested == datetime.timedelta(days=90)


def test_request_emails_the_whole_team(client, auth_headers, monkeypatch, db_session):
    sent = _capture_emails(monkeypatch)
    owner = db_session.query(User).filter(User.email == "ada@example.com").one()
    db_session.add(User(org_id=owner.org_id, email="staff@example.com", hashed_password="x", email_verified=True, role=UserRole.staff))
    db_session.commit()

    _close(client, auth_headers)
    assert sorted(to for to, _ in sent) == ["ada@example.com", "staff@example.com"]
    assert all("will be closed" in subject for _, subject in sent)


def test_only_a_signed_in_owner_can_close_or_cancel(client, auth_headers, db_session):
    key = client.post("/api/api-keys", json={"name": "k"}, headers=auth_headers).json()["key"]
    assert _close(client, {"Authorization": f"Bearer {key}"}).status_code == 403

    owner = db_session.query(User).filter(User.email == "ada@example.com").one()
    owner.role = UserRole.staff
    db_session.commit()
    assert _close(client, auth_headers).status_code == 403
    owner.role = UserRole.owner
    db_session.commit()

    _close(client, auth_headers)
    owner.role = UserRole.staff
    db_session.commit()
    assert client.delete("/api/account/closure", headers=auth_headers).status_code == 403


def test_closing_account_is_read_only_but_viewable_and_exportable(client, auth_headers):
    customer = client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers).json()
    _close(client, auth_headers)

    blocked = client.post("/api/customers", json={"name": "New"}, headers=auth_headers)
    assert blocked.status_code == 423 and "read-only" in blocked.json()["detail"]
    assert client.patch(f"/api/customers/{customer['id']}", json={"name": "X"}, headers=auth_headers).status_code == 423
    assert client.delete(f"/api/customers/{customer['id']}", headers=auth_headers).status_code == 423
    assert client.post("/api/messages/send", json={"customer_ids": [customer["id"]], "subject": "x", "body_html": "x"}, headers=auth_headers).status_code == 423

    # reading, exporting, previews and notifications still work
    assert client.get("/api/customers", headers=auth_headers).json()["total"] == 1
    assert client.get("/api/customers/export", headers=auth_headers).status_code == 200
    assert client.post("/api/messages/preview", json={"customer_id": customer["id"], "subject": "x", "body_html": "x"}, headers=auth_headers).status_code == 200
    assert client.post("/api/notifications/read-all", headers=auth_headers).status_code in (200, 204)

    # API keys are read-only too
    key_resp = client.post("/api/api-keys", json={"name": "k"}, headers=auth_headers)
    assert key_resp.status_code == 423


def test_public_forms_stop_taking_entries(client, auth_headers):
    form = client.post("/api/forms", json={"name": "Leads", "fields": FORM_FIELDS}, headers=auth_headers).json()
    _close(client, auth_headers)
    assert client.get(f"/api/public/forms/{form['public_token']}").status_code == 404
    assert client.post(f"/api/public/forms/{form['public_token']}/submit", json={"first_name": "Z"}).status_code == 404


def test_cancel_reopens_the_account(client, auth_headers, monkeypatch):
    sent = _capture_emails(monkeypatch)
    _close(client, auth_headers)
    resp = client.delete("/api/account/closure", headers=auth_headers)
    assert resp.status_code == 200 and resp.json()["closing"] is False
    assert client.post("/api/customers", json={"name": "Back in business"}, headers=auth_headers).status_code == 201
    assert any("staying open" in subject for _, subject in sent)
    assert client.delete("/api/account/closure", headers=auth_headers).status_code == 409


def test_requesting_twice_keeps_the_original_date(client, auth_headers):
    first = _close(client, auth_headers).json()
    second = _close(client, auth_headers).json()
    assert first["scheduled_for"] == second["scheduled_for"]


# --- the deletion -------------------------------------------------------------


def _row_counts(db) -> dict[str, int]:
    return {t.name: db.execute(select(func.count()).select_from(t)).scalar() for t in Base.metadata.sorted_tables}


def _fill_with_data(client, headers, db, org_email):
    """Puts something in as many tables as the app writes to."""
    c1 = client.post("/api/customers", json={"first_name": "Ada", "last_name": "Obi", "email": "c1@x.com", "consent_date": "2026-01-01"}, headers=headers).json()
    c2 = client.post("/api/customers", json={"name": "Bo Chen", "extra": {"Shoe": "42"}}, headers=headers).json()
    client.post(f"/api/customers/{c1['id']}/transactions", json={"date": "2026-11-01", "items": [{"item": "Rice", "amount": 5}]}, headers={**headers, "Idempotency-Key": f"k-{org_email}"})
    client.post(f"/api/customers/{c1['id']}/orders", json={"order_date": "2026-11-01", "items": [{"name": "Oil"}]}, headers=headers)
    client.post("/api/notes", json={"title": "n", "content": "shared", "customer_ids": [c1["id"], c2["id"]]}, headers=headers)
    client.post("/api/segments", json={"name": "All"}, headers=headers)
    client.post("/api/messages/templates", json={"name": "T", "subject": "S", "body_html": "<p>B</p>"}, headers=headers)
    client.post("/api/messages/send", json={"customer_ids": [c1["id"]], "subject": "Hi", "body_html": "<p>x</p>"}, headers=headers)
    form = client.post("/api/forms", json={"name": "Leads", "fields": FORM_FIELDS}, headers=headers).json()
    client.post(f"/api/public/forms/{form['public_token']}/submit", json={"first_name": "Cy"})
    client.post("/api/api-keys", json={"name": "k"}, headers=headers)
    client.put("/api/settings", json={"industry": "Retail"}, headers=headers)
    client.post("/api/auth/forgot-password", json={"email": org_email})

    user = db.query(User).filter(User.email == org_email).one()
    thread_id = str(uuid.uuid4())
    sub = WebhookSubscription(org_id=user.org_id, target_url="https://example.com/hook", event_types=["customer.created"])
    db.add_all([ChatThread(id=thread_id, org_id=user.org_id, user_id=user.id), sub])
    db.flush()
    db.add_all(
        [
            ChatMessage(thread_id=thread_id, role="user", content="hello"),
            PendingAction(org_id=user.org_id, user_id=user.id, tool_name="delete_customer", payload={}, description="d"),
            AgentAction(org_id=user.org_id, user_id=user.id, tool_name="create_customer", payload={}, result={}),
            SavedWidget(org_id=user.org_id, user_id=user.id, question="q", title="t"),
            DocumentScan(org_id=user.org_id, user_id=user.id, image_hash=org_email, status="done", extracted={}, actions=[]),
            WebhookDelivery(org_id=user.org_id, subscription_id=sub.id, event_type="customer.created", payload={}, status="success"),
        ]
    )
    db.commit()
    return user.org_id


def test_purge_deletes_everything_of_one_business_and_nothing_else(client, auth_headers, db_session, monkeypatch):
    sent = _capture_emails(monkeypatch)
    other_headers = _signup(client, "Other Co", "other@example.com")
    _fill_with_data(client, other_headers, db_session, "other@example.com")
    # Ada's own business and login already exist (the auth_headers fixture
    # made them) - take them out, so this is what's left with Ada gone
    from app.models.auth_token import AuthToken

    ada = db_session.query(User).filter(User.email == "ada@example.com").one()
    counts_with_only_other = _row_counts(db_session)
    counts_with_only_other["organizations"] -= 1
    counts_with_only_other["users"] -= 1
    counts_with_only_other["auth_tokens"] -= db_session.query(AuthToken).filter(AuthToken.user_id == ada.id).count()

    org_id = _fill_with_data(client, auth_headers, db_session, "ada@example.com")
    filled = _row_counts(db_session)
    # the business really had data in every table
    empty_for_ada = [t for t in filled if filled[t] == counts_with_only_other[t]]
    assert empty_for_ada == [], f"test seeds nothing into: {empty_for_ada}"

    _close(client, auth_headers)
    org = db_session.get(Organization, org_id)
    org.closure_scheduled_for = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=1)
    db_session.commit()
    sent.clear()

    # SQLite ignores foreign keys unless told otherwise; Postgres doesn't. Turn
    # them on so a wrong deletion order fails here rather than in production.
    from tests.conftest import engine

    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")
        assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
    try:
        assert closure.purge_due(db_session) == 1
        with engine.connect() as conn:
            assert conn.exec_driver_sql("PRAGMA foreign_key_check").fetchall() == []
    finally:
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    db_session.expire_all()
    assert _row_counts(db_session) == counts_with_only_other
    assert db_session.get(Organization, org_id) is None
    assert [(to, "deleted" in subject) for to, subject in sent] == [("ada@example.com", True)]

    # the deleted login is gone; the other business carries on
    assert client.post("/api/auth/login", json={"email": "ada@example.com", "password": "secret123"}).status_code == 401
    assert client.get("/api/customers", headers=other_headers).json()["total"] == 3
    # and the email address can sign up again from scratch
    assert client.post("/api/auth/signup", json={"org_name": "Ada Again", "email": "ada@example.com", "password": "secret123"}).status_code == 201


def test_purge_leaves_accounts_that_are_not_due(client, auth_headers, db_session):
    client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)
    _close(client, auth_headers)
    assert closure.purge_due(db_session) == 0
    assert client.get("/api/customers", headers=auth_headers).json()["total"] == 1
