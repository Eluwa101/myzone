"""
run_chat's thread-id namespacing, tested directly without a real model:
create_agent is stubbed to capture the config it's invoked with.
"""
import app.agent.runner as runner


class _FakeMessage:
    def __init__(self, content):
        self.content = content
        self.type = "ai"


class _FakeAgent:
    def __init__(self, sink):
        self._sink = sink

    def invoke(self, payload, config):
        self._sink.append(config)
        return {"messages": [_FakeMessage("ok")]}


def test_thread_id_is_namespaced_under_org_and_user(db_session, seeded_org, monkeypatch):
    org_id, user_id = seeded_org
    captured_configs = []
    monkeypatch.setattr(runner, "get_model", lambda: None)  # avoid a real network call to Groq/Gemini
    monkeypatch.setattr(runner, "create_agent", lambda **kwargs: _FakeAgent(captured_configs))

    runner.run_chat(db_session, org_id, user_id, "hello", thread_id="my-chat")
    assert captured_configs[-1]["configurable"]["thread_id"] == f"{org_id}:{user_id}:my-chat"

    runner.run_chat(db_session, org_id, user_id, "hello again", thread_id=None)
    assert captured_configs[-1]["configurable"]["thread_id"] == f"{org_id}:{user_id}:default"

    runner.run_chat(db_session, org_id, user_id, "hello", thread_id="other-chat")
    assert captured_configs[-1]["configurable"]["thread_id"] != captured_configs[-3]["configurable"]["thread_id"]
