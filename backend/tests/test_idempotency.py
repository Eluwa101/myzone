def test_repeated_create_with_same_key_does_not_duplicate(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "11111111-1111-1111-1111-111111111111"}

    first = client.post("/api/customers", json={"name": "Ada Obi"}, headers=headers)
    assert first.status_code == 201

    second = client.post("/api/customers", json={"name": "Ada Obi"}, headers=headers)
    assert second.status_code == 201
    assert second.json()["id"] == first.json()["id"]
    assert second.headers.get("x-idempotent-replay") == "true"

    listed = client.get("/api/customers", headers=auth_headers).json()
    assert listed["total"] == 1


def test_different_key_creates_separately(client, auth_headers):
    first = client.post(
        "/api/customers", json={"name": "Ada Obi"}, headers={**auth_headers, "Idempotency-Key": "key-a"}
    )
    second = client.post(
        "/api/customers", json={"name": "Bo Diaz"}, headers={**auth_headers, "Idempotency-Key": "key-b"}
    )
    assert first.json()["id"] != second.json()["id"]

    listed = client.get("/api/customers", headers=auth_headers).json()
    assert listed["total"] == 2


def test_failed_request_is_not_cached_and_can_be_retried(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "retry-key"}

    bad = client.post("/api/customers", json={}, headers=headers)
    assert bad.status_code == 422

    good = client.post("/api/customers", json={"name": "Ada Obi"}, headers=headers)
    assert good.status_code == 201
    assert "x-idempotent-replay" not in good.headers


def test_no_header_behaves_normally(client, auth_headers):
    first = client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)
    second = client.post("/api/customers", json={"name": "Bo Diaz"}, headers=auth_headers)
    assert first.json()["id"] != second.json()["id"]


def test_key_is_scoped_to_method_and_path(client, auth_headers):
    headers = {**auth_headers, "Idempotency-Key": "shared-key"}
    created = client.post("/api/customers", json={"name": "Ada Obi"}, headers=headers)
    customer_id = created.json()["id"]

    # Same key, different route (an update) - must not be served from the
    # create's cached response.
    updated = client.patch(f"/api/customers/{customer_id}", json={"job": "Tailor"}, headers=headers)
    assert updated.status_code == 200
    assert updated.json()["job"] == "Tailor"
    assert "x-idempotent-replay" not in updated.headers


def test_get_requests_are_never_cached(client, auth_headers):
    client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)
    headers = {**auth_headers, "Idempotency-Key": "get-key"}
    first = client.get("/api/customers", headers=headers)
    client.post("/api/customers", json={"name": "Bo Diaz"}, headers=auth_headers)
    second = client.get("/api/customers", headers=headers)
    assert first.json()["total"] == 1
    assert second.json()["total"] == 2
