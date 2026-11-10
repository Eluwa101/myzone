def test_create_customer_defaults_to_customer_status(client, auth_headers):
    resp = client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "customer"
    assert body["status_auto"] is True


def test_create_customer_from_first_last_name_derives_name(client, auth_headers):
    resp = client.post(
        "/api/customers",
        json={"first_name": "Ada", "last_name": "Obi"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Ada Obi"
    assert body["first_name"] == "Ada"
    assert body["last_name"] == "Obi"


def test_create_customer_without_name_or_first_last_is_rejected(client, auth_headers):
    resp = client.post("/api/customers", json={"phone": "08012345678"}, headers=auth_headers)
    assert resp.status_code == 422


def test_update_first_name_resyncs_name(client, auth_headers):
    created = client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers).json()

    resp = client.patch(
        f"/api/customers/{created['id']}",
        json={"first_name": "Chioma", "last_name": "Obi"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "Chioma Obi"


def test_create_customer_with_interests_is_a_lead(client, auth_headers):
    resp = client.post(
        "/api/customers",
        json={"name": "Ada Obi", "interests": "Generator, Rice"},
        headers=auth_headers,
    )
    assert resp.json()["status"] == "lead"


def test_duplicate_phone_is_flagged_unless_forced(client, auth_headers):
    client.post("/api/customers", json={"name": "Ada Obi", "phone": "08012345678"}, headers=auth_headers)
    resp = client.post("/api/customers", json={"name": "Ada O.", "phone": "+234 801 234 5678"}, headers=auth_headers)
    assert resp.status_code == 409
    existing_id = resp.json()["detail"]["existing_id"]

    forced = client.post(
        "/api/customers",
        json={"name": "Ada O.", "phone": "+234 801 234 5678"},
        params={"force": True},
        headers=auth_headers,
    )
    assert forced.status_code == 201
    assert forced.json()["id"] != existing_id


def test_add_transaction_flips_status_and_clears_bought_interest(client, auth_headers):
    created = client.post(
        "/api/customers",
        json={"name": "Ada Obi", "interests": "Rice, Generator"},
        headers=auth_headers,
    ).json()
    assert created["status"] == "lead"

    tx_resp = client.post(
        f"/api/customers/{created['id']}/transactions",
        json={"date": "2026-11-01", "items": [{"item": "Rice", "qty": 2, "amount": 15000}], "currency": "NGN"},
        headers=auth_headers,
    )
    assert tx_resp.status_code == 201

    updated = client.get(f"/api/customers/{created['id']}", headers=auth_headers).json()
    assert updated["status"] == "customer"
    assert updated["interests"] == "Generator"


def test_manual_status_is_pinned(client, auth_headers):
    created = client.post(
        "/api/customers",
        json={"name": "Ada Obi", "status": "inactive"},
        headers=auth_headers,
    ).json()
    assert created["status"] == "inactive"
    assert created["status_auto"] is False

    client.post(
        f"/api/customers/{created['id']}/transactions",
        json={"date": "2026-11-01", "items": [{"item": "Rice", "amount": 1000}], "currency": "NGN"},
        headers=auth_headers,
    )
    unchanged = client.get(f"/api/customers/{created['id']}", headers=auth_headers).json()
    assert unchanged["status"] == "inactive"


def test_find_and_merge_duplicates(client, auth_headers):
    a = client.post(
        "/api/customers",
        json={"name": "Ada Obi", "email": "ada@mail.com", "notes": "nurse"},
        headers=auth_headers,
    ).json()
    b = client.post(
        "/api/customers",
        json={"name": "Ada Obi", "email": "ada@mail.com", "pet": "Dog - Max"},
        params={"force": True},
        headers=auth_headers,
    ).json()

    groups = client.get("/api/customers/duplicates", headers=auth_headers).json()
    assert len(groups) == 1
    assert groups[0]["keep"]["id"] == a["id"]

    merged = client.post(
        "/api/customers/merge",
        json={"keep_id": a["id"], "merge_id": b["id"]},
        headers=auth_headers,
    )
    assert merged.status_code == 200
    body = merged.json()
    assert body["pet"] == "Dog - Max"
    assert body["notes"] == "nurse"

    gone = client.get(f"/api/customers/{b['id']}", headers=auth_headers)
    assert gone.status_code == 404


def test_csv_export_then_import_round_trips_without_duplicating(client, auth_headers):
    created = client.post(
        "/api/customers",
        json={"name": "Ada Obi", "phone": "08012345678"},
        headers=auth_headers,
    ).json()
    client.post(
        f"/api/customers/{created['id']}/transactions",
        json={"date": "2026-11-01", "items": [{"item": "Rice", "qty": 1, "amount": 15000}], "currency": "NGN"},
        headers=auth_headers,
    )

    csv_text = client.get("/api/customers/export", headers=auth_headers).text
    assert "Ada Obi" in csv_text

    result = client.post("/api/customers/import", json={"csv_text": csv_text}, headers=auth_headers).json()
    assert result["added"] == 0
    assert result["merged"] == 1

    listing = client.get("/api/customers", headers=auth_headers).json()
    assert listing["total"] == 1
