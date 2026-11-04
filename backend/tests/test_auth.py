def test_signup_and_me(client):
    resp = client.post(
        "/api/auth/signup",
        json={"org_name": "Ada's Store", "email": "ada@example.com", "password": "supersecret"},
    )
    assert resp.status_code == 201
    token = resp.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "ada@example.com"


def test_signup_duplicate_email_rejected(client):
    payload = {"org_name": "Ada's Store", "email": "ada@example.com", "password": "supersecret"}
    client.post("/api/auth/signup", json=payload)
    resp = client.post("/api/auth/signup", json=payload)
    assert resp.status_code == 409


def test_login_wrong_password_rejected(client):
    client.post(
        "/api/auth/signup",
        json={"org_name": "Ada's Store", "email": "ada@example.com", "password": "supersecret"},
    )
    resp = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_customer_routes_require_auth(client):
    resp = client.get("/api/customers")
    assert resp.status_code == 401
