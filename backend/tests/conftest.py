import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.controllers import messaging_controller, scan_controller, webhook_controller
from app.core import idempotency
from app.core.database import Base, get_db
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# webhook_controller._deliver runs on a background thread and opens its own
# session directly (it can't use the get_db dependency override, since
# nothing injects it there) - point it at the same test engine, or a
# webhook test would silently try to write delivery rows to whatever real
# DATABASE_URL happens to be configured on the machine running the tests.
webhook_controller.SessionLocal = TestingSessionLocal

# IdempotencyMiddleware runs outside the request's dependency-injected
# session too (middleware has no access to get_db overrides), so it needs
# the same redirect to the test engine.
idempotency.SessionLocal = TestingSessionLocal

# messaging_controller's batch email sender runs on its own background
# thread with its own session too, same reason as webhook_controller above.
messaging_controller.SessionLocal = TestingSessionLocal
scan_controller.SessionLocal = TestingSessionLocal


@pytest.fixture(autouse=True)
def _no_real_email(monkeypatch):
    """Tests must never reach Resend. Without this, every signup sent a
    real verification email using whatever RESEND_API_KEY backend/.env
    has, and an email sent from a background thread could outlive its
    test and write into the next test's fresh database. Tests that check
    what gets sent replace send_raw themselves."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "resend_api_key", None)
    monkeypatch.setattr(messaging_controller, "_start_in_background", lambda target, *args: target(*args))
    monkeypatch.setattr(scan_controller, "_start_in_background", lambda target, *args: target(*args))


@pytest.fixture(autouse=True)
def _fresh_schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def verify_user_email(email: str) -> None:
    """Test helper: marks a signed-up user's email verified directly,
    bypassing the real email-link flow - used wherever a test needs a
    second/other account to log in without caring about verification
    itself (that flow has its own tests in test_auth.py)."""
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        user.email_verified = True
        db.commit()
    finally:
        db.close()


def _override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = _override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def seeded_org(db_session):
    from app.core.security import hash_password
    from app.models.organization import Organization
    from app.models.user import User

    org = Organization(name="Ada's Store")
    db_session.add(org)
    db_session.flush()
    user = User(org_id=org.id, email="ada@example.com", hashed_password=hash_password("supersecret"), email_verified=True)
    db_session.add(user)
    db_session.commit()
    return org.id, user.id


@pytest.fixture
def auth_headers(client):
    client.post(
        "/api/auth/signup",
        json={"org_name": "Ada's Store", "email": "ada@example.com", "password": "supersecret"},
    )
    # signup requires email verification before login - tests care about
    # what happens after login, not the verification flow itself, so mark
    # it verified directly rather than threading a captured token through
    # every test that needs auth_headers.
    verify_user_email("ada@example.com")

    resp = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "supersecret"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
