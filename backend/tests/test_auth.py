from app.controllers import auth_controller


def _signup(client, email="ada@example.com", password="supersecret", org_name="Ada's Store"):
    return client.post("/api/auth/signup", json={"org_name": org_name, "email": email, "password": password})


def test_signup_requires_verification_before_login(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(auth_controller, "send_verification_email", lambda to, token, **kw: captured.update(to=to, token=token))

    resp = _signup(client)
    assert resp.status_code == 201
    assert resp.json() == {"status": "verification_required", "email": "ada@example.com"}
    assert "access_token" not in resp.json()
    assert captured["to"] == "ada@example.com"

    # can't log in yet - unverified
    blocked = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "supersecret"})
    assert blocked.status_code == 403
    assert blocked.json()["detail"]["code"] == "email_not_verified"

    verified = client.post("/api/auth/verify-email", json={"token": captured["token"]})
    assert verified.status_code == 200
    token = verified.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email_verified"] is True

    # now login works too
    login = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "supersecret"})
    assert login.status_code == 200


def test_verify_email_rejects_unknown_or_reused_token(client, monkeypatch):
    captured = {}
    monkeypatch.setattr(auth_controller, "send_verification_email", lambda to, token, **kw: captured.update(token=token))
    _signup(client)

    bad = client.post("/api/auth/verify-email", json={"token": "not-a-real-token"})
    assert bad.status_code == 400

    first = client.post("/api/auth/verify-email", json={"token": captured["token"]})
    assert first.status_code == 200

    replay = client.post("/api/auth/verify-email", json={"token": captured["token"]})
    assert replay.status_code == 400


def test_resend_verification_does_not_reveal_whether_email_exists(client, monkeypatch):
    sent = []
    monkeypatch.setattr(auth_controller, "send_verification_email", lambda to, token, **kw: sent.append(to))
    _signup(client)

    known = client.post("/api/auth/resend-verification", json={"email": "ada@example.com"})
    unknown = client.post("/api/auth/resend-verification", json={"email": "nobody@example.com"})
    assert known.status_code == 200
    assert unknown.status_code == 200
    assert known.json() == unknown.json() == {"status": "ok"}
    # one from signup itself, one from the resend - "nobody@example.com" got none
    assert sent == ["ada@example.com", "ada@example.com"]


def test_verification_email_is_branded_with_org_name_and_support_email(client, monkeypatch, db_session):
    captured = {}
    monkeypatch.setattr(
        auth_controller,
        "send_verification_email",
        lambda to, token, **kw: captured.update(to=to, from_name=kw.get("from_name"), reply_to=kw.get("reply_to")),
    )

    _signup(client, org_name="Ada's Store")
    # right after signup there's no org_settings row yet - falls back to the
    # org name itself for the display name, and no reply-to
    assert captured["from_name"] == "Ada's Store via MyShop"
    assert captured["reply_to"] is None

    from app.models.org_settings import OrgSettings
    from app.models.user import User

    user = db_session.query(User).filter(User.email == "ada@example.com").first()
    db_session.add(OrgSettings(org_id=user.org_id, biz_name="Ada's Boutique", support_email="ada@realmail.com"))
    db_session.commit()

    resend_resp = client.post("/api/auth/resend-verification", json={"email": "ada@example.com"})
    assert resend_resp.status_code == 200
    assert captured["from_name"] == "Ada's Boutique via MyShop"
    assert captured["reply_to"] == "ada@realmail.com"


def test_signup_duplicate_email_rejected(client):
    _signup(client)
    resp = _signup(client)
    assert resp.status_code == 409


def test_login_wrong_password_rejected(client):
    from tests.conftest import verify_user_email

    _signup(client)
    verify_user_email("ada@example.com")
    resp = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "wrong"})
    assert resp.status_code == 401


def test_customer_routes_require_auth(client):
    resp = client.get("/api/customers")
    assert resp.status_code == 401


def test_forgot_password_then_reset_logs_in_with_new_password(client, monkeypatch):
    from tests.conftest import verify_user_email

    captured = {}
    monkeypatch.setattr(auth_controller, "send_verification_email", lambda to, token, **kw: None)
    monkeypatch.setattr(auth_controller, "send_password_reset_email", lambda to, token, **kw: captured.update(to=to, token=token))

    _signup(client)
    verify_user_email("ada@example.com")

    forgot = client.post("/api/auth/forgot-password", json={"email": "ada@example.com"})
    assert forgot.status_code == 200
    assert captured["to"] == "ada@example.com"

    reset = client.post("/api/auth/reset-password", json={"token": captured["token"], "new_password": "brandnewpass"})
    assert reset.status_code == 200
    assert "access_token" in reset.json()

    old_login = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "supersecret"})
    assert old_login.status_code == 401

    new_login = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "brandnewpass"})
    assert new_login.status_code == 200


def test_forgot_password_unknown_email_is_silent(client):
    resp = client.post("/api/auth/forgot-password", json={"email": "nobody@example.com"})
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_reset_password_rejects_unknown_or_reused_token(client, monkeypatch):
    from tests.conftest import verify_user_email

    captured = {}
    monkeypatch.setattr(auth_controller, "send_verification_email", lambda to, token, **kw: None)
    monkeypatch.setattr(auth_controller, "send_password_reset_email", lambda to, token, **kw: captured.update(token=token))
    _signup(client)
    verify_user_email("ada@example.com")
    client.post("/api/auth/forgot-password", json={"email": "ada@example.com"})

    bad = client.post("/api/auth/reset-password", json={"token": "nope", "new_password": "whatever1"})
    assert bad.status_code == 400

    first = client.post("/api/auth/reset-password", json={"token": captured["token"], "new_password": "brandnewpass"})
    assert first.status_code == 200

    replay = client.post("/api/auth/reset-password", json={"token": captured["token"], "new_password": "anotherpass"})
    assert replay.status_code == 400


def test_forgot_password_on_google_only_account_sends_notice_not_reset_link(client, db_session, monkeypatch):
    from app.models.organization import Organization
    from app.models.user import User

    org = Organization(name="Google Co")
    db_session.add(org)
    db_session.flush()
    db_session.add(User(org_id=org.id, email="g@example.com", hashed_password=None, google_sub="abc123", email_verified=True))
    db_session.commit()

    notice_sent = []
    reset_sent = []
    monkeypatch.setattr(auth_controller, "send_google_only_account_notice", lambda to, **kw: notice_sent.append(to))
    monkeypatch.setattr(auth_controller, "send_password_reset_email", lambda to, token, **kw: reset_sent.append(to))

    resp = client.post("/api/auth/forgot-password", json={"email": "g@example.com"})

    assert resp.status_code == 200
    assert notice_sent == ["g@example.com"]
    assert reset_sent == []


def test_google_auth_creates_new_account_and_org(client, monkeypatch):
    def fake_verify(credential):
        return {"sub": "google-sub-1", "email": "newperson@example.com", "email_verified": True, "name": "New Person"}

    monkeypatch.setattr("app.controllers.auth_controller.verify_google_id_token", fake_verify)

    resp = client.post("/api/auth/google", json={"credential": "fake-id-token"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["email"] == "newperson@example.com"
    assert me["email_verified"] is True


def test_google_auth_links_to_existing_password_account_by_email(client, monkeypatch):
    from tests.conftest import verify_user_email

    _signup(client)
    verify_user_email("ada@example.com")
    before = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "supersecret"}).json()
    before_user_id = client.get("/api/auth/me", headers={"Authorization": f"Bearer {before['access_token']}"}).json()["id"]

    def fake_verify(credential):
        return {"sub": "google-sub-2", "email": "ada@example.com", "email_verified": True, "name": "Ada"}

    monkeypatch.setattr("app.controllers.auth_controller.verify_google_id_token", fake_verify)

    resp = client.post("/api/auth/google", json={"credential": "fake-id-token"})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    after_user_id = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).json()["id"]
    assert after_user_id == before_user_id  # linked, not duplicated


def test_google_auth_rejects_invalid_credential(client, monkeypatch):
    from app.core.google_auth import InvalidGoogleTokenError

    def fake_verify(credential):
        raise InvalidGoogleTokenError("Invalid or expired Google credential.")

    monkeypatch.setattr("app.controllers.auth_controller.verify_google_id_token", fake_verify)

    resp = client.post("/api/auth/google", json={"credential": "garbage"})
    assert resp.status_code == 401
