"""
Chat history persistence, exercised via the real /api/agent/chat route with
run_chat mocked (no LLM needed - we're testing our own persistence wiring,
not the model's output) plus direct controller tests for list/get/delete.
"""
import app.routes.agent as agent_routes
from app.controllers import chat_history_controller


def _mock_run_chat(monkeypatch, reply="Hi there!"):
    def fake_run_chat(db, org_id, user_id, message, thread_id=None, image_data_url=None):
        return reply, []

    monkeypatch.setattr(agent_routes, "run_chat", fake_run_chat)


def test_sending_a_message_creates_a_thread_with_a_title(client, auth_headers, monkeypatch):
    _mock_run_chat(monkeypatch)
    client.post("/api/agent/chat", json={"message": "How many customers do I have?", "thread_id": "t1"}, headers=auth_headers)

    threads = client.get("/api/agent/threads", headers=auth_headers).json()
    assert len(threads) == 1
    assert threads[0]["id"] == "t1"
    assert threads[0]["title"] == "How many customers do I have?"


def test_thread_title_does_not_change_on_later_messages(client, auth_headers, monkeypatch):
    _mock_run_chat(monkeypatch)
    client.post("/api/agent/chat", json={"message": "first message", "thread_id": "t1"}, headers=auth_headers)
    client.post("/api/agent/chat", json={"message": "second message", "thread_id": "t1"}, headers=auth_headers)

    threads = client.get("/api/agent/threads", headers=auth_headers).json()
    assert len(threads) == 1
    assert threads[0]["title"] == "first message"


def test_thread_messages_are_recorded_in_order(client, auth_headers, monkeypatch):
    _mock_run_chat(monkeypatch, reply="reply one")
    client.post("/api/agent/chat", json={"message": "question one", "thread_id": "t1"}, headers=auth_headers)
    _mock_run_chat(monkeypatch, reply="reply two")
    client.post("/api/agent/chat", json={"message": "question two", "thread_id": "t1"}, headers=auth_headers)

    messages = client.get("/api/agent/threads/t1/messages", headers=auth_headers).json()
    assert [(m["role"], m["content"]) for m in messages] == [
        ("user", "question one"),
        ("assistant", "reply one"),
        ("user", "question two"),
        ("assistant", "reply two"),
    ]


def test_different_thread_ids_stay_separate(client, auth_headers, monkeypatch):
    _mock_run_chat(monkeypatch, reply="a")
    client.post("/api/agent/chat", json={"message": "in thread one", "thread_id": "t1"}, headers=auth_headers)
    _mock_run_chat(monkeypatch, reply="b")
    client.post("/api/agent/chat", json={"message": "in thread two", "thread_id": "t2"}, headers=auth_headers)

    threads = client.get("/api/agent/threads", headers=auth_headers).json()
    assert {t["id"] for t in threads} == {"t1", "t2"}

    t1_messages = client.get("/api/agent/threads/t1/messages", headers=auth_headers).json()
    assert [m["content"] for m in t1_messages] == ["in thread one", "a"]


def test_deleting_a_thread_removes_it_and_its_messages(client, auth_headers, monkeypatch):
    _mock_run_chat(monkeypatch)
    client.post("/api/agent/chat", json={"message": "hello", "thread_id": "t1"}, headers=auth_headers)

    resp = client.delete("/api/agent/threads/t1", headers=auth_headers)
    assert resp.status_code == 204

    assert client.get("/api/agent/threads", headers=auth_headers).json() == []
    assert client.get("/api/agent/threads/t1/messages", headers=auth_headers).status_code == 404


def test_cannot_fetch_another_orgs_thread(client, auth_headers, db_session, monkeypatch):
    _mock_run_chat(monkeypatch)
    client.post("/api/agent/chat", json={"message": "hello", "thread_id": "t1"}, headers=auth_headers)

    from app.core.security import hash_password
    from app.models.organization import Organization
    from app.models.user import User

    other_org = Organization(name="Someone Else's Store")
    db_session.add(other_org)
    db_session.flush()
    other_user = User(org_id=other_org.id, email="other@example.com", hashed_password=hash_password("supersecret"))
    db_session.add(other_user)
    db_session.commit()

    import app.core.security as security

    other_token = security.create_access_token(other_user.id, other_org.id)
    other_headers = {"Authorization": f"Bearer {other_token}"}

    assert client.get("/api/agent/threads", headers=other_headers).json() == []
    assert client.get("/api/agent/threads/t1/messages", headers=other_headers).status_code == 404


def test_image_flag_is_recorded(client, auth_headers, monkeypatch, db_session):
    _mock_run_chat(monkeypatch)
    client.post(
        "/api/agent/chat",
        json={"message": "what's on this page?", "thread_id": "t1", "image_data_url": "data:image/png;base64,AAAA"},
        headers=auth_headers,
    )
    messages = client.get("/api/agent/threads/t1/messages", headers=auth_headers).json()
    assert messages[0]["has_image"] is True
    assert messages[1]["has_image"] is False


def test_title_falls_back_for_blank_message(db_session, seeded_org):
    org_id, user_id = seeded_org
    chat_history_controller.record_user_message(db_session, org_id, user_id, "t1", "   ")
    threads = chat_history_controller.list_threads(db_session, org_id, user_id)
    assert threads[0].title == "New chat"
