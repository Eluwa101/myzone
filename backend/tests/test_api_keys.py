"""API keys: creating, using, revoking, and what a key may not do."""
from app.core.api_keys import hash_key
from app.models.api_key import ApiKey


def _create_key(client, auth_headers, name="Zapier"):
    resp = client.post("/api/api-keys", json={"name": name}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_key_returns_it_once_and_stores_only_a_hash(client, auth_headers, db_session):
    created = _create_key(client, auth_headers)
    assert created["key"].startswith("msk_live_") and len(created["key"]) > 40
    assert created["key"].startswith(created["prefix"])

    listed = client.get("/api/api-keys", headers=auth_headers).json()
    assert len(listed) == 1 and "key" not in listed[0] and listed[0]["name"] == "Zapier"

    stored = db_session.query(ApiKey).one()
    assert stored.key_hash == hash_key(created["key"])
    assert created["key"] not in (stored.prefix, stored.key_hash, stored.name)


def test_key_works_like_a_login(client, auth_headers):
    key = _create_key(client, auth_headers)["key"]
    headers = {"Authorization": f"Bearer {key}"}

    created = client.post("/api/customers", json={"name": "Ada Obi"}, headers=headers)
    assert created.status_code == 201
    listed = client.get("/api/customers", headers=auth_headers).json()
    assert [c["name"] for c in listed["items"]] == ["Ada Obi"]  # same business as the creator

    tx = client.post(
        f"/api/customers/{created.json()['id']}/transactions",
        json={"date": "2026-11-01", "items": [{"item": "Rice", "amount": 500}]},
        headers=headers,
    )
    assert tx.status_code == 201
    assert client.get("/api/api-keys", headers=auth_headers).json()[0]["last_used_at"] is not None


def test_key_only_sees_its_own_business(client, auth_headers):
    from tests.conftest import verify_user_email

    client.post("/api/customers", json={"name": "Ada's customer"}, headers=auth_headers)
    client.post("/api/auth/signup", json={"org_name": "Other Co", "email": "o@example.com", "password": "secret123"})
    verify_user_email("o@example.com")
    other_token = client.post("/api/auth/login", json={"email": "o@example.com", "password": "secret123"}).json()["access_token"]
    other_key = _create_key(client, {"Authorization": f"Bearer {other_token}"})["key"]

    seen = client.get("/api/customers", headers={"Authorization": f"Bearer {other_key}"}).json()
    assert seen["total"] == 0


def test_revoked_or_made_up_keys_are_rejected(client, auth_headers):
    created = _create_key(client, auth_headers)
    headers = {"Authorization": f"Bearer {created['key']}"}
    assert client.get("/api/customers", headers=headers).status_code == 200

    assert client.delete(f"/api/api-keys/{created['id']}", headers=auth_headers).status_code == 204
    resp = client.get("/api/customers", headers=headers)
    assert resp.status_code == 401 and resp.json()["detail"] == "Invalid or revoked API key"
    assert client.get("/api/api-keys", headers=auth_headers).json()[0]["revoked_at"] is not None

    assert client.get("/api/customers", headers={"Authorization": "Bearer msk_live_madeup"}).status_code == 401


def test_a_key_cannot_manage_keys(client, auth_headers):
    created = _create_key(client, auth_headers)
    headers = {"Authorization": f"Bearer {created['key']}"}
    assert client.post("/api/api-keys", json={"name": "sneaky"}, headers=headers).status_code == 403
    assert client.get("/api/api-keys", headers=headers).status_code == 403
    assert client.delete(f"/api/api-keys/{created['id']}", headers=headers).status_code == 403


def test_cannot_revoke_another_business_key(client, auth_headers):
    from tests.conftest import verify_user_email

    client.post("/api/auth/signup", json={"org_name": "Other Co", "email": "o2@example.com", "password": "secret123"})
    verify_user_email("o2@example.com")
    other_token = client.post("/api/auth/login", json={"email": "o2@example.com", "password": "secret123"}).json()["access_token"]
    theirs = _create_key(client, {"Authorization": f"Bearer {other_token}"})
    assert client.delete(f"/api/api-keys/{theirs['id']}", headers=auth_headers).status_code == 404


def test_idempotency_key_works_with_api_keys(client, auth_headers):
    key = _create_key(client, auth_headers)["key"]
    headers = {"Authorization": f"Bearer {key}", "Idempotency-Key": "retry-1"}
    first = client.post("/api/customers", json={"name": "Once Only"}, headers=headers)
    second = client.post("/api/customers", json={"name": "Once Only"}, headers=headers)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] == second.json()["id"]
    assert client.get("/api/customers", headers=auth_headers).json()["total"] == 1


def test_key_management_requires_auth(client):
    assert client.get("/api/api-keys").status_code == 401
