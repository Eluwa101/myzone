FIRST_NAME_FIELD = {"key": "first_name", "label": "First name", "type": "text", "required": True, "category": "customer"}
LAST_NAME_FIELD = {"key": "last_name", "label": "Last name", "type": "text", "required": False, "category": "customer"}
PHONE_FIELD = {"key": "phone", "label": "Phone", "type": "tel", "required": False, "category": "customer"}
EMAIL_FIELD = {"key": "email", "label": "Email", "type": "email", "required": False, "category": "customer"}
CORE_CONTACT_FIELDS = [FIRST_NAME_FIELD, LAST_NAME_FIELD, PHONE_FIELD, EMAIL_FIELD]
CUSTOM_FIELD = {"key": "fav_color", "label": "Favorite color", "type": "text", "required": False, "category": "custom"}
TX_ITEM_FIELD = {"key": "tx_item", "label": "Item", "type": "text", "required": False, "category": "transaction"}
TX_AMOUNT_FIELD = {"key": "tx_amount", "label": "Amount", "type": "number", "required": False, "category": "transaction"}
ORDER_ITEM_FIELD = {"key": "order_item", "label": "Item ordered", "type": "text", "required": False, "category": "order"}
ORDER_PRICE_FIELD = {"key": "order_price", "label": "Price", "type": "number", "required": False, "category": "order"}
ORDER_QTY_FIELD = {"key": "order_qty", "label": "Quantity", "type": "number", "required": False, "category": "order"}


def _create_form(client, auth_headers, fields=None):
    return client.post(
        "/api/forms",
        json={"name": "Lead intake", "fields": fields or [*CORE_CONTACT_FIELDS, CUSTOM_FIELD]},
        headers=auth_headers,
    ).json()


def test_create_form_requires_core_contact_fields(client, auth_headers):
    resp = client.post("/api/forms", json={"name": "Bad form", "fields": [PHONE_FIELD]}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_form_requires_first_name_to_be_required(client, auth_headers):
    not_required = {**FIRST_NAME_FIELD, "required": False}
    resp = client.post(
        "/api/forms",
        json={"name": "Bad form", "fields": [not_required, LAST_NAME_FIELD, PHONE_FIELD, EMAIL_FIELD]},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_and_list_forms(client, auth_headers):
    form = _create_form(client, auth_headers)
    assert form["public_token"]
    assert form["is_active"] is True

    listing = client.get("/api/forms", headers=auth_headers).json()
    assert len(listing) == 1
    assert listing[0]["id"] == form["id"]


def test_public_form_metadata_hides_org_id(client, auth_headers):
    form = _create_form(client, auth_headers)
    resp = client.get(f"/api/public/forms/{form['public_token']}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "Lead intake"
    assert "org_id" not in body
    assert "id" not in body


def test_public_form_business_name_falls_back_to_org_name(client, auth_headers):
    form = _create_form(client, auth_headers)
    resp = client.get(f"/api/public/forms/{form['public_token']}")
    assert resp.json()["business_name"] == "Ada's Store"


def test_public_form_business_name_uses_biz_name_when_set(client, auth_headers):
    client.put("/api/settings", json={"biz_name": "Ada's Fabrics"}, headers=auth_headers)
    form = _create_form(client, auth_headers)
    resp = client.get(f"/api/public/forms/{form['public_token']}")
    assert resp.json()["business_name"] == "Ada's Fabrics"


def test_public_submission_creates_customer_with_extra_field(client, auth_headers):
    form = _create_form(client, auth_headers)
    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit",
        json={"first_name": "Ada", "last_name": "Obi", "phone": "08012345678", "fav_color": "Blue"},
    )
    assert resp.status_code == 200
    assert resp.json()["customer_created"] is True

    customers = client.get("/api/customers", headers=auth_headers).json()["items"]
    assert len(customers) == 1
    assert customers[0]["name"] == "Ada Obi"
    assert customers[0]["first_name"] == "Ada"
    assert customers[0]["last_name"] == "Obi"
    assert customers[0]["extra"]["Favorite color"] == "Blue"


def test_public_submission_merges_into_existing_customer_by_phone(client, auth_headers):
    form = _create_form(client, auth_headers)
    client.post("/api/customers", json={"name": "Ada Obi", "phone": "08012345678"}, headers=auth_headers)

    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit",
        json={"first_name": "Ada", "last_name": "O.", "phone": "08012345678", "fav_color": "Green"},
    )
    assert resp.status_code == 200
    assert resp.json()["customer_created"] is False

    customers = client.get("/api/customers", headers=auth_headers).json()["items"]
    assert len(customers) == 1
    assert customers[0]["extra"]["Favorite color"] == "Green"


def test_public_submission_missing_required_field_is_rejected(client, auth_headers):
    form = _create_form(client, auth_headers)
    resp = client.post(f"/api/public/forms/{form['public_token']}/submit", json={"phone": "08012345678"})
    assert resp.status_code == 400
    assert "first name" in resp.json()["detail"].lower()


def test_inactive_form_is_not_publicly_reachable(client, auth_headers):
    form = _create_form(client, auth_headers)
    client.patch(f"/api/forms/{form['id']}", json={"is_active": False}, headers=auth_headers)
    resp = client.get(f"/api/public/forms/{form['public_token']}")
    assert resp.status_code == 404


def test_regenerate_token_invalidates_old_link(client, auth_headers):
    form = _create_form(client, auth_headers)
    old_token = form["public_token"]
    updated = client.patch(f"/api/forms/{form['id']}", json={"regenerate_token": True}, headers=auth_headers).json()
    assert updated["public_token"] != old_token
    assert client.get(f"/api/public/forms/{old_token}").status_code == 404
    assert client.get(f"/api/public/forms/{updated['public_token']}").status_code == 200


def test_submissions_are_listed_for_the_owning_org(client, auth_headers):
    form = _create_form(client, auth_headers)
    client.post(f"/api/public/forms/{form['public_token']}/submit", json={"first_name": "Ada", "last_name": "Obi"})
    submissions = client.get(f"/api/forms/{form['id']}/submissions", headers=auth_headers).json()
    assert len(submissions) == 1
    assert submissions[0]["raw_payload"]["first_name"] == "Ada"


def test_delete_form(client, auth_headers):
    form = _create_form(client, auth_headers)
    resp = client.delete(f"/api/forms/{form['id']}", headers=auth_headers)
    assert resp.status_code == 204
    assert client.get("/api/forms", headers=auth_headers).json() == []


def test_submission_with_transaction_fields_logs_a_transaction(client, auth_headers):
    form = _create_form(client, auth_headers, fields=[*CORE_CONTACT_FIELDS, TX_ITEM_FIELD, TX_AMOUNT_FIELD])
    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit",
        json={"first_name": "Ada", "last_name": "Obi", "tx_item": "Rice", "tx_amount": "15000"},
    )
    assert resp.status_code == 200
    assert resp.json()["transaction_logged"] is True

    customers = client.get("/api/customers", headers=auth_headers).json()["items"]
    assert len(customers[0]["transactions"]) == 1
    assert customers[0]["transactions"][0]["items"] == [{"item": "Rice", "qty": 1, "amount": 15000}]
    assert customers[0]["transactions"][0]["amount"] == 15000


def test_submission_without_amount_does_not_log_a_transaction(client, auth_headers):
    form = _create_form(client, auth_headers, fields=[*CORE_CONTACT_FIELDS, TX_ITEM_FIELD, TX_AMOUNT_FIELD])
    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit", json={"first_name": "Ada", "last_name": "Obi", "tx_item": "Rice"}
    )
    assert resp.status_code == 200
    assert resp.json()["transaction_logged"] is False

    customers = client.get("/api/customers", headers=auth_headers).json()["items"]
    assert customers[0]["transactions"] == []


def test_submission_with_order_fields_logs_an_order(client, auth_headers):
    form = _create_form(client, auth_headers, fields=[*CORE_CONTACT_FIELDS, ORDER_ITEM_FIELD, ORDER_QTY_FIELD, ORDER_PRICE_FIELD])
    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit",
        json={"first_name": "Ada", "last_name": "Obi", "order_item": "Generator", "order_qty": "2", "order_price": "45000"},
    )
    assert resp.status_code == 200
    assert resp.json()["order_logged"] is True

    customers = client.get("/api/customers", headers=auth_headers).json()["items"]
    assert len(customers[0]["orders"]) == 1
    order = customers[0]["orders"][0]
    assert order["items"] == [{"name": "Generator", "qty": 2, "price": 45000}]
    assert order["amount"] == 90000


def test_submission_without_order_item_does_not_log_an_order(client, auth_headers):
    form = _create_form(client, auth_headers, fields=[*CORE_CONTACT_FIELDS, ORDER_ITEM_FIELD])
    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit", json={"first_name": "Ada", "last_name": "Obi"}
    )
    assert resp.status_code == 200
    assert resp.json()["order_logged"] is False


def test_submission_customer_name_shown_in_submissions_list(client, auth_headers):
    form = _create_form(client, auth_headers)
    client.post(f"/api/public/forms/{form['public_token']}/submit", json={"first_name": "Ada", "last_name": "Obi"})
    submissions = client.get(f"/api/forms/{form['id']}/submissions", headers=auth_headers).json()
    assert submissions[0]["customer_name"] == "Ada Obi"


# --- incoming webhook behavior: arbitrary JSON + optional signing ----------


def test_submission_accepts_non_string_json_values(client, auth_headers):
    """A real webhook sender (e.g. Zapier) sends native JSON types, not
    everything pre-stringified - qty as a number, not "2"."""
    form = _create_form(client, auth_headers, fields=[*CORE_CONTACT_FIELDS, TX_ITEM_FIELD, TX_AMOUNT_FIELD])
    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit",
        json={"first_name": "Ada", "last_name": "Obi", "tx_item": "Rice", "tx_amount": 500},
    )
    assert resp.status_code == 200
    assert resp.json()["transaction_logged"] is True


def test_submission_rejects_non_object_body(client, auth_headers):
    form = _create_form(client, auth_headers)
    resp = client.post(f"/api/public/forms/{form['public_token']}/submit", json=["not", "an", "object"])
    assert resp.status_code == 400


def test_enable_signing_requires_valid_signature(client, auth_headers):
    import hashlib
    import hmac
    import json

    form = _create_form(client, auth_headers)
    form = client.patch(f"/api/forms/{form['id']}", json={"enable_signing": True}, headers=auth_headers).json()
    assert form["webhook_secret"]

    body = {"first_name": "Ada", "last_name": "Obi"}
    raw = json.dumps(body).encode()

    # missing signature
    resp = client.post(f"/api/public/forms/{form['public_token']}/submit", content=raw, headers={"Content-Type": "application/json"})
    assert resp.status_code == 401

    # wrong signature
    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit",
        content=raw,
        headers={"Content-Type": "application/json", "X-Signature": "deadbeef"},
    )
    assert resp.status_code == 401

    # correct signature
    sig = hmac.new(form["webhook_secret"].encode(), raw, hashlib.sha256).hexdigest()
    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit",
        content=raw,
        headers={"Content-Type": "application/json", "X-Signature": sig},
    )
    assert resp.status_code == 200


def test_disable_signing_removes_secret_and_requirement(client, auth_headers):
    form = _create_form(client, auth_headers)
    form = client.patch(f"/api/forms/{form['id']}", json={"enable_signing": True}, headers=auth_headers).json()
    form = client.patch(f"/api/forms/{form['id']}", json={"disable_signing": True}, headers=auth_headers).json()
    assert form["webhook_secret"] is None

    resp = client.post(f"/api/public/forms/{form['public_token']}/submit", json={"first_name": "Ada", "last_name": "Obi"})
    assert resp.status_code == 200


def test_regenerate_signing_secret_invalidates_old_signature(client, auth_headers):
    import hashlib
    import hmac
    import json

    form = _create_form(client, auth_headers)
    form = client.patch(f"/api/forms/{form['id']}", json={"enable_signing": True}, headers=auth_headers).json()
    old_secret = form["webhook_secret"]

    form = client.patch(f"/api/forms/{form['id']}", json={"enable_signing": True}, headers=auth_headers).json()
    assert form["webhook_secret"] != old_secret

    body = {"first_name": "Ada", "last_name": "Obi"}
    raw = json.dumps(body).encode()
    stale_sig = hmac.new(old_secret.encode(), raw, hashlib.sha256).hexdigest()
    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit",
        content=raw,
        headers={"Content-Type": "application/json", "X-Signature": stale_sig},
    )
    assert resp.status_code == 401
