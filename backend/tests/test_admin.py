"""Platform admins opening another business's account to help."""
import pytest

from app.core.config import settings
from app.models.admin_access_log import AdminAccessLog
from app.models.user import User
from tests.conftest import verify_user_email


def _signup(client, org_name, email):
    client.post("/api/auth/signup", json={"org_name": org_name, "email": email, "password": "secret123"})
    verify_user_email(email)
    token = client.post("/api/auth/login", json={"email": email, "password": "secret123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin(client, monkeypatch):
    """ada@example.com (the auth_headers user) is the platform admin; Bo runs
    another business."""
    monkeypatch.setattr(settings, "platform_admin_emails", " Ada@Example.com , someone@else.com")
    bo = _signup(client, "Bo's Laundry", "bo@example.com")
    bo_org = client.get("/api/auth/me", headers=bo).json()["org_id"]
    return {"bo": bo, "bo_org": bo_org}


def _enter(client, auth_headers, org_id):
    resp = client.post("/api/admin/impersonate", json={"org_id": org_id}, headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}, resp.json()


def test_admin_sees_every_business(client, auth_headers, admin):
    client.post("/api/customers", json={"name": "Bo's customer"}, headers=admin["bo"])
    orgs = client.get("/api/admin/orgs", headers=auth_headers).json()
    assert [o["name"] for o in orgs] == ["Ada's Store", "Bo's Laundry"]  # own business first
    assert orgs[0]["is_home"] is True
    assert orgs[1]["owner_email"] == "bo@example.com" and orgs[1]["customers"] == 1
    assert client.get("/api/auth/me", headers=auth_headers).json()["is_platform_admin"] is True


def test_non_admins_get_nothing(client, auth_headers, admin):
    assert client.get("/api/admin/orgs", headers=admin["bo"]).status_code == 403
    ada_org = client.get("/api/auth/me", headers=auth_headers).json()["org_id"]
    assert client.post("/api/admin/impersonate", json={"org_id": ada_org}, headers=admin["bo"]).status_code == 403
    assert client.get("/api/auth/me", headers=admin["bo"]).json()["is_platform_admin"] is False


def test_no_admins_configured_means_no_admin(client, auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "platform_admin_emails", "")
    assert client.get("/api/admin/orgs", headers=auth_headers).status_code == 403


def test_admin_works_inside_the_other_business(client, auth_headers, admin, db_session):
    client.post("/api/customers", json={"name": "Ada's own customer"}, headers=auth_headers)
    bo_customer = client.post("/api/customers", json={"name": "Bo's customer"}, headers=admin["bo"]).json()
    inside, session = _enter(client, auth_headers, admin["bo_org"])
    assert session["org_name"] == "Bo's Laundry"

    me = client.get("/api/auth/me", headers=inside).json()
    assert me["org_id"] == admin["bo_org"] and me["email"] == "ada@example.com" and me["admin_session"] is True

    # sees and changes Bo's data, not Ada's
    assert [c["name"] for c in client.get("/api/customers", headers=inside).json()["items"]] == ["Bo's customer"]
    assert client.patch(f"/api/customers/{bo_customer['id']}", json={"phone": "0801"}, headers=inside).status_code == 200
    created = client.post("/api/customers", json={"name": "Added by support"}, headers=inside)
    assert created.status_code == 201
    assert client.get("/api/customers", headers=admin["bo"]).json()["total"] == 2
    assert client.get("/api/customers", headers=auth_headers).json()["total"] == 1

    # the admin's own account still belongs to their own business
    db_session.expire_all()
    ada = db_session.query(User).filter(User.email == "ada@example.com").one()
    assert str(ada.org_id) != admin["bo_org"]


def test_business_is_told_and_everything_is_logged(client, auth_headers, admin, db_session):
    inside, _ = _enter(client, auth_headers, admin["bo_org"])
    client.post("/api/customers", json={"name": "Added by support"}, headers=inside)
    client.get("/api/customers", headers=inside)  # reads aren't logged
    assert client.post("/api/admin/stop", headers=inside).status_code == 204

    bell = client.get("/api/notifications", headers=admin["bo"]).json()
    assert bell[0]["type"] == "admin.access" and bell[0]["title"] == "MyShop support opened your account to help"
    assert "every change made is logged" in bell[0]["body"]

    logs = db_session.query(AdminAccessLog).order_by(AdminAccessLog.created_at, AdminAccessLog.kind).all()
    kinds = [(l.kind, l.method, l.path) for l in logs]
    assert ("switch", None, None) in kinds
    assert ("request", "POST", "/api/customers") in kinds
    assert ("end", None, None) in kinds
    assert all(str(l.org_id) == admin["bo_org"] and l.admin_email == "ada@example.com" for l in logs)


def test_some_things_are_off_limits_in_an_admin_session(client, auth_headers, admin):
    inside, _ = _enter(client, auth_headers, admin["bo_org"])
    assert client.post("/api/account/closure", json={"confirm_name": "Bo's Laundry"}, headers=inside).status_code == 403
    assert client.post("/api/api-keys", json={"name": "k"}, headers=inside).status_code == 403
    assert client.get("/api/account/closure", headers=admin["bo"]).json()["closing"] is False


def test_removing_admin_rights_ends_open_sessions(client, auth_headers, admin, monkeypatch):
    inside, _ = _enter(client, auth_headers, admin["bo_org"])
    monkeypatch.setattr(settings, "platform_admin_emails", "")
    assert client.get("/api/customers", headers=inside).status_code == 401


def test_cannot_impersonate_own_or_missing_business(client, auth_headers, admin):
    ada_org = client.get("/api/auth/me", headers=auth_headers).json()["org_id"]
    assert client.post("/api/admin/impersonate", json={"org_id": ada_org}, headers=auth_headers).status_code == 422
    missing = "00000000-0000-0000-0000-000000000000"
    assert client.post("/api/admin/impersonate", json={"org_id": missing}, headers=auth_headers).status_code == 404


def test_switch_straight_from_one_business_to_another(client, auth_headers, admin):
    cy = _signup(client, "Cy's Cleaners", "cy@example.com")
    cy_org = client.get("/api/auth/me", headers=cy).json()["org_id"]
    inside_bo, _ = _enter(client, auth_headers, admin["bo_org"])
    inside_cy, session = _enter(client, inside_bo, cy_org)
    assert session["org_name"] == "Cy's Cleaners"
    assert client.get("/api/auth/me", headers=inside_cy).json()["org_id"] == cy_org


def test_a_forged_admin_token_is_rejected(client, admin):
    """A normal user can't mint an act_as token for themselves: it's signed,
    and even a validly signed one only works for a listed admin."""
    from uuid import UUID

    from app.core.security import create_admin_session_token

    bo_me = client.get("/api/auth/me", headers=admin["bo"]).json()
    token, _ = create_admin_session_token(UUID(bo_me["id"]), UUID(bo_me["org_id"]))
    assert client.get("/api/customers", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_admin_can_see_whether_a_business_is_closing(client, auth_headers, admin):
    client.post("/api/account/closure", json={"confirm_name": "Bo's Laundry"}, headers=admin["bo"])
    inside, _ = _enter(client, auth_headers, admin["bo_org"])
    resp = client.get("/api/account/closure", headers=inside)
    assert resp.status_code == 200 and resp.json()["closing"] is True
