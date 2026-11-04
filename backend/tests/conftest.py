import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _fresh_schema():
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


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
    user = User(org_id=org.id, email="ada@example.com", hashed_password=hash_password("supersecret"))
    db_session.add(user)
    db_session.commit()
    return org.id, user.id


@pytest.fixture
def auth_headers(client):
    client.post(
        "/api/auth/signup",
        json={"org_name": "Ada's Store", "email": "ada@example.com", "password": "supersecret"},
    )
    resp = client.post("/api/auth/login", json={"email": "ada@example.com", "password": "supersecret"})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
