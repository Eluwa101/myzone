def _create_customer(client, auth_headers, name="Ada Obi"):
    return client.post("/api/customers", json={"name": name}, headers=auth_headers).json()


def test_multi_item_checkout_is_one_transaction_not_several(client, auth_headers):
    """The bug this guards against: a single checkout with several line
    items used to be sent as one POST per line, creating a separate
    Transaction row per item. One POST with several items must create
    exactly one transaction."""
    customer = _create_customer(client, auth_headers)
    resp = client.post(
        f"/api/customers/{customer['id']}/transactions",
        json={
            "date": "2026-11-01",
            "items": [
                {"item": "Rice", "qty": 2, "amount": 5000},
                {"item": "Sugar", "qty": 1, "amount": 1200},
            ],
            "currency": "NGN",
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    tx = resp.json()
    assert tx["amount"] == 6200
    assert tx["items"] == [
        {"item": "Rice", "qty": 2, "amount": 5000},
        {"item": "Sugar", "qty": 1, "amount": 1200},
    ]

    listed = client.get(f"/api/customers/{customer['id']}", headers=auth_headers).json()
    assert len(listed["transactions"]) == 1


def test_update_transaction_replaces_item_list(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    created = client.post(
        f"/api/customers/{customer['id']}/transactions",
        json={"date": "2026-11-01", "items": [{"item": "Rice", "qty": 1, "amount": 5000}], "currency": "NGN"},
        headers=auth_headers,
    ).json()

    updated = client.patch(
        f"/api/customers/{customer['id']}/transactions/{created['id']}",
        json={"items": [{"item": "Rice", "qty": 1, "amount": 5000}, {"item": "Beans", "qty": 2, "amount": 3000}]},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["amount"] == 8000
    assert len(body["items"]) == 2


def test_update_transaction_currency_only_keeps_items(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    created = client.post(
        f"/api/customers/{customer['id']}/transactions",
        json={"date": "2026-11-01", "items": [{"item": "Rice", "qty": 1, "amount": 5000}], "currency": "NGN"},
        headers=auth_headers,
    ).json()

    updated = client.patch(
        f"/api/customers/{customer['id']}/transactions/{created['id']}",
        json={"currency": "USD"},
        headers=auth_headers,
    ).json()
    assert updated["currency"] == "USD"
    assert updated["items"] == [{"item": "Rice", "qty": 1, "amount": 5000}]
    assert updated["amount"] == 5000


def test_delete_transaction(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    created = client.post(
        f"/api/customers/{customer['id']}/transactions",
        json={"date": "2026-11-01", "items": [{"item": "Rice", "qty": 1, "amount": 5000}], "currency": "NGN"},
        headers=auth_headers,
    ).json()

    resp = client.delete(f"/api/customers/{customer['id']}/transactions/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204

    listed = client.get(f"/api/customers/{customer['id']}", headers=auth_headers).json()
    assert listed["transactions"] == []


def test_add_transaction_requires_at_least_one_item(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    resp = client.post(
        f"/api/customers/{customer['id']}/transactions",
        json={"date": "2026-11-01", "items": [], "currency": "NGN"},
        headers=auth_headers,
    )
    assert resp.status_code == 422
