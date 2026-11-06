def _create_customer(client, auth_headers, name="Ada Obi"):
    return client.post("/api/customers", json={"name": name}, headers=auth_headers).json()


def test_create_order_defaults_and_appears_on_customer(client, auth_headers):
    customer = _create_customer(client, auth_headers)

    resp = client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": "2026-11-05", "delivery_date": "2026-11-10", "items": [{"name": "Rice", "qty": 2}], "amount": 15000, "currency": "NGN"},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["paid"] is False
    assert body["delivered"] is False
    assert body["items"] == [{"name": "Rice", "qty": 2, "price": None}]

    updated_customer = client.get(f"/api/customers/{customer['id']}", headers=auth_headers).json()
    assert len(updated_customer["orders"]) == 1
    assert updated_customer["orders"][0]["id"] == body["id"]


def test_order_items_support_price_per_line(client, auth_headers):
    customer = _create_customer(client, auth_headers)

    resp = client.post(
        f"/api/customers/{customer['id']}/orders",
        json={
            "order_date": "2026-11-05",
            "items": [{"name": "Rice", "qty": 2, "price": 2500}, {"name": "Generator", "qty": 1, "price": 45000}],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["items"] == [
        {"name": "Rice", "qty": 2, "price": 2500},
        {"name": "Generator", "qty": 1, "price": 45000},
    ]


def test_update_order_toggles_paid_and_delivered(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    created = client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": "2026-11-05", "items": [{"name": "Generator"}]},
        headers=auth_headers,
    ).json()

    resp = client.patch(
        f"/api/customers/{customer['id']}/orders/{created['id']}",
        json={"paid": True, "delivered": True},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["paid"] is True
    assert body["delivered"] is True


def test_delete_order(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    created = client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": "2026-11-05", "items": [{"name": "Rice"}]},
        headers=auth_headers,
    ).json()

    resp = client.delete(f"/api/customers/{customer['id']}/orders/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204

    listing = client.get(f"/api/customers/{customer['id']}/orders", headers=auth_headers).json()
    assert listing == []


def test_order_scoped_to_customer_and_org(client, auth_headers):
    customer_a = _create_customer(client, auth_headers, name="Ada Obi")
    customer_b = _create_customer(client, auth_headers, name="Bola Ade")
    order = client.post(
        f"/api/customers/{customer_a['id']}/orders",
        json={"order_date": "2026-11-05", "items": [{"name": "Rice"}]},
        headers=auth_headers,
    ).json()

    resp = client.patch(
        f"/api/customers/{customer_b['id']}/orders/{order['id']}",
        json={"paid": True},
        headers=auth_headers,
    )
    assert resp.status_code == 404


def test_orders_require_auth(client):
    resp = client.get("/api/customers/00000000-0000-0000-0000-000000000000/orders")
    assert resp.status_code == 401
