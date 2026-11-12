EMPTY_SETTINGS = {
    "biz_name": None,
    "whatsapp_number": None,
    "qr_message": None,
    "industry": None,
    "team_size": None,
    "phone": None,
    "address": None,
    "brand_color": None,
    "manager_name": None,
    "staff_names": None,
    "default_currency": None,
    "support_email": None,
    # generated from the org name ("Ada's Store") the first time settings
    # are read; the domain is whatever EMAIL_FROM's address is on
    "sender_handle": "adasstore",
    "sender_domain": "resend.dev",
}


def test_get_settings_creates_default_row(client, auth_headers):
    resp = client.get("/api/settings", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == EMPTY_SETTINGS


def test_update_settings_persists(client, auth_headers):
    resp = client.put(
        "/api/settings",
        json={"biz_name": "Ada's Store", "whatsapp_number": "2348012345678", "qr_message": "Hi there!"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {
        **EMPTY_SETTINGS,
        "biz_name": "Ada's Store",
        "whatsapp_number": "2348012345678",
        "qr_message": "Hi there!",
    }

    again = client.get("/api/settings", headers=auth_headers).json()
    assert again["biz_name"] == "Ada's Store"


def test_partial_update_keeps_other_fields(client, auth_headers):
    client.put("/api/settings", json={"biz_name": "Ada's Store"}, headers=auth_headers)
    resp = client.put("/api/settings", json={"whatsapp_number": "2348012345678"}, headers=auth_headers)
    assert resp.json() == {
        **EMPTY_SETTINGS,
        "biz_name": "Ada's Store",
        "whatsapp_number": "2348012345678",
    }


def test_update_org_profile_fields(client, auth_headers):
    resp = client.put(
        "/api/settings",
        json={
            "industry": "Retail",
            "team_size": 5,
            "phone": "2348012345678",
            "address": "12 Market Rd, Lagos",
            "brand_color": "#4f46e5",
            "manager_name": "Ada",
            "staff_names": ["Jane", "Kemi"],
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {
        **EMPTY_SETTINGS,
        "industry": "Retail",
        "team_size": 5,
        "phone": "2348012345678",
        "address": "12 Market Rd, Lagos",
        "brand_color": "#4f46e5",
        "manager_name": "Ada",
        "staff_names": ["Jane", "Kemi"],
    }


def test_update_default_currency(client, auth_headers):
    resp = client.put("/api/settings", json={"default_currency": "NGN"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["default_currency"] == "NGN"

    again = client.get("/api/settings", headers=auth_headers).json()
    assert again["default_currency"] == "NGN"


def _other_org_headers(client, email="other@example.com", org_name="Ada's Store"):
    from tests.conftest import verify_user_email

    client.post("/api/auth/signup", json={"org_name": org_name, "email": email, "password": "secret123"})
    verify_user_email(email)
    token = client.post("/api/auth/login", json={"email": email, "password": "secret123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_sender_handle_is_unique_across_orgs(client, auth_headers):
    first = client.get("/api/settings", headers=auth_headers).json()["sender_handle"]
    second = client.get("/api/settings", headers=_other_org_headers(client), ).json()["sender_handle"]
    assert first == "adasstore"
    assert second == "adasstore2"


def test_update_sender_handle_normalizes_it(client, auth_headers):
    resp = client.put("/api/settings", json={"sender_handle": "Ada Boutique!"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["sender_handle"] == "adaboutique"


def test_update_sender_handle_rejects_reserved_short_and_taken(client, auth_headers):
    client.get("/api/settings", headers=auth_headers)  # claims "adasstore"
    other = _other_org_headers(client, org_name="Bo's Shop")

    assert client.put("/api/settings", json={"sender_handle": "notifications"}, headers=other).status_code == 422
    assert client.put("/api/settings", json={"sender_handle": "ab"}, headers=other).status_code == 422
    assert client.put("/api/settings", json={"sender_handle": "adasstore"}, headers=other).status_code == 422
    # a rejected handle leaves the existing one in place
    assert client.get("/api/settings", headers=other).json()["sender_handle"] == "bosshop"


def test_reserved_business_name_does_not_get_a_reserved_handle(client):
    headers = _other_org_headers(client, email="s@example.com", org_name="Support")
    assert client.get("/api/settings", headers=headers).json()["sender_handle"] == "supportshop"
