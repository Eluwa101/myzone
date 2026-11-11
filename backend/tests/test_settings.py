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
