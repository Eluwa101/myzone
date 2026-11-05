"""
Smoke test against whatever DATABASE_URL is configured in backend/.env
(currently Supabase). Unlike the pytest suite (which runs against an
in-memory SQLite DB), this hits the real configured database end to end,
then cleans up everything it created.

Run from backend/:
    .venv/Scripts/python scripts/smoke_test.py
"""
import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.core.config import settings
from app.core.database import SessionLocal
from app.main import app
from app.models.agent_action import AgentAction
from app.models.chat_message import ChatMessage
from app.models.chat_thread import ChatThread
from app.models.customer import Customer
from app.models.organization import Organization
from app.models.pending_action import PendingAction
from app.models.transaction import Transaction
from app.models.user import User

email = f"smoketest+{uuid.uuid4().hex[:8]}@example.com"
password = "supersecret1"
failures: list[str] = []


def check(label: str, condition: bool, detail: str = ""):
    status = "OK" if condition else "FAIL"
    print(f"[{status}] {label}{(' - ' + detail) if detail and not condition else ''}")
    if not condition:
        failures.append(label)


def cleanup(org_id: str | None):
    if not org_id:
        return
    db = SessionLocal()
    try:
        # LangGraph's own checkpoint tables, keyed by "{org_id}:{user_id}:{thread_id}"
        for table in ("checkpoint_writes", "checkpoint_blobs", "checkpoints"):
            db.execute(text(f"DELETE FROM {table} WHERE thread_id LIKE :prefix"), {"prefix": f"{org_id}:%"})
        db.query(AgentAction).filter(AgentAction.org_id == org_id).delete(synchronize_session=False)
        db.query(PendingAction).filter(PendingAction.org_id == org_id).delete(synchronize_session=False)
        thread_ids = [t.id for t in db.query(ChatThread).filter(ChatThread.org_id == org_id).all()]
        if thread_ids:
            db.query(ChatMessage).filter(ChatMessage.thread_id.in_(thread_ids)).delete(synchronize_session=False)
        db.query(ChatThread).filter(ChatThread.org_id == org_id).delete(synchronize_session=False)
        db.query(Transaction).filter(
            Transaction.customer_id.in_(db.query(Customer.id).filter(Customer.org_id == org_id))
        ).delete(synchronize_session=False)
        db.query(Customer).filter(Customer.org_id == org_id).delete(synchronize_session=False)
        db.query(User).filter(User.org_id == org_id).delete(synchronize_session=False)
        db.query(Organization).filter(Organization.id == org_id).delete(synchronize_session=False)
        db.commit()
        print(f"[cleanup] removed smoke-test org {org_id}")
    finally:
        db.close()


def main(client: TestClient) -> int:
    org_id = None
    start = time.time()

    resp = client.get("/api/health")
    check("health check", resp.status_code == 200 and resp.json().get("status") == "ok")

    resp = client.post("/api/auth/signup", json={"org_name": "Smoke Test Co", "email": email, "password": password})
    check("signup", resp.status_code == 201, resp.text)
    token = resp.json().get("access_token") if resp.status_code == 201 else None
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    check("login", resp.status_code == 200, resp.text)

    resp = client.get("/api/auth/me", headers=headers)
    check("authenticated /me", resp.status_code == 200 and resp.json().get("email") == email, resp.text)
    org_id = resp.json().get("org_id") if resp.status_code == 200 else None

    resp = client.post("/api/customers", json={"name": "Smoke Test Customer", "interests": "Generator"}, headers=headers)
    check("create customer (lead)", resp.status_code == 201 and resp.json().get("status") == "lead", resp.text)
    customer_id = resp.json().get("id") if resp.status_code == 201 else None

    if customer_id:
        resp = client.post(
            f"/api/customers/{customer_id}/transactions",
            json={"date": "2026-11-01", "item": "Generator", "qty": 1, "amount": 50000, "currency": "NGN"},
            headers=headers,
        )
        check("add transaction", resp.status_code == 201, resp.text)

        resp = client.get(f"/api/customers/{customer_id}", headers=headers)
        check("status flips to customer after purchase", resp.status_code == 200 and resp.json().get("status") == "customer", resp.text)

    resp = client.get("/api/summary", headers=headers)
    check("summary endpoint", resp.status_code == 200 and resp.json().get("total_customers", 0) >= 1, resp.text)

    if settings.groq_api_key or settings.google_api_key:
        resp = client.post("/api/agent/chat", json={"message": "How many customers do I have?"}, headers=headers)
        reply = resp.json().get("reply") if resp.status_code == 200 else None
        check("agent chat", resp.status_code == 200 and bool(reply), resp.text)
    else:
        print("[skip] agent chat - no GROQ_API_KEY or GOOGLE_API_KEY set in backend/.env")

    cleanup(org_id)

    elapsed = time.time() - start
    print(f"\n{len(failures)} failing check(s) out of smoke test, {elapsed:.1f}s")
    return 1 if failures else 0


if __name__ == "__main__":
    # used as a context manager so FastAPI's lifespan shutdown runs,
    # closing the checkpointer's connection pool cleanly on exit
    with TestClient(app) as test_client:
        sys.exit(main(test_client))
