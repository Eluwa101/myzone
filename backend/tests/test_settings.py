def test_get_settings_creates_default_row(client, auth_headers):
    resp = client.get("/api/settings", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json() == {"biz_name": None, "whatsapp_number": None, "qr_message": None}


def test_update_settings_persists(client, auth_headers):
    resp = client.put(
        "/api/settings",
        json={"biz_name": "Ada's Store", "whatsapp_number": "2348012345678", "qr_message": "Hi there!"},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json() == {"biz_name": "Ada's Store", "whatsapp_number": "2348012345678", "qr_message": "Hi there!"}

    again = client.get("/api/settings", headers=auth_headers).json()
    assert again["biz_name"] == "Ada's Store"


def test_partial_update_keeps_other_fields(client, auth_headers):
    client.put("/api/settings", json={"biz_name": "Ada's Store"}, headers=auth_headers)
    resp = client.put("/api/settings", json={"whatsapp_number": "2348012345678"}, headers=auth_headers)
    assert resp.json() == {"biz_name": "Ada's Store", "whatsapp_number": "2348012345678", "qr_message": None}
