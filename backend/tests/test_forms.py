NAME_FIELD = {"key": "name", "label": "Full name", "type": "text", "required": True, "standard": True}
PHONE_FIELD = {"key": "phone", "label": "Phone", "type": "tel", "required": False, "standard": True}
CUSTOM_FIELD = {"key": "fav_color", "label": "Favorite color", "type": "text", "required": False, "standard": False}


def _create_form(client, auth_headers, fields=None):
    return client.post(
        "/api/forms",
        json={"name": "Lead intake", "fields": fields or [NAME_FIELD, PHONE_FIELD, CUSTOM_FIELD]},
        headers=auth_headers,
    ).json()


def test_create_form_requires_a_required_name_field(client, auth_headers):
    resp = client.post("/api/forms", json={"name": "Bad form", "fields": [PHONE_FIELD]}, headers=auth_headers)
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


def test_public_submission_creates_customer_with_extra_field(client, auth_headers):
    form = _create_form(client, auth_headers)
    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit",
        json={"name": "Ada Obi", "phone": "08012345678", "fav_color": "Blue"},
    )
    assert resp.status_code == 200
    assert resp.json()["customer_created"] is True

    customers = client.get("/api/customers", headers=auth_headers).json()["items"]
    assert len(customers) == 1
    assert customers[0]["name"] == "Ada Obi"
    assert customers[0]["extra"]["Favorite color"] == "Blue"


def test_public_submission_merges_into_existing_customer_by_phone(client, auth_headers):
    form = _create_form(client, auth_headers)
    client.post("/api/customers", json={"name": "Ada Obi", "phone": "08012345678"}, headers=auth_headers)

    resp = client.post(
        f"/api/public/forms/{form['public_token']}/submit",
        json={"name": "Ada O.", "phone": "08012345678", "fav_color": "Green"},
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
    assert "name" in resp.json()["detail"].lower() or "full name" in resp.json()["detail"].lower()


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
    client.post(f"/api/public/forms/{form['public_token']}/submit", json={"name": "Ada Obi"})
    submissions = client.get(f"/api/forms/{form['id']}/submissions", headers=auth_headers).json()
    assert len(submissions) == 1
    assert submissions[0]["raw_payload"]["name"] == "Ada Obi"


def test_delete_form(client, auth_headers):
    form = _create_form(client, auth_headers)
    resp = client.delete(f"/api/forms/{form['id']}", headers=auth_headers)
    assert resp.status_code == 204
    assert client.get("/api/forms", headers=auth_headers).json() == []
