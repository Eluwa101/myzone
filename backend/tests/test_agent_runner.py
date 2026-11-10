"""
run_chat's thread-id namespacing, tested directly without a real model:
create_agent is stubbed to capture the config it's invoked with.
"""
import pytest

import app.agent.runner as runner
from app.controllers import customer_controller, notification_controller, settings_controller
from app.schemas.customer import CustomerCreate
from app.schemas.settings import SettingsUpdate


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
    monkeypatch.setattr(runner, "get_checkpointer", lambda: None)  # avoid a real connection to Postgres
    monkeypatch.setattr(runner, "create_agent", lambda **kwargs: _FakeAgent(captured_configs))

    runner.run_chat(db_session, org_id, user_id, "hello", thread_id="my-chat")
    assert captured_configs[-1]["configurable"]["thread_id"] == f"{org_id}:{user_id}:my-chat"

    runner.run_chat(db_session, org_id, user_id, "hello again", thread_id=None)
    assert captured_configs[-1]["configurable"]["thread_id"] == f"{org_id}:{user_id}:default"

    runner.run_chat(db_session, org_id, user_id, "hello", thread_id="other-chat")
    assert captured_configs[-1]["configurable"]["thread_id"] != captured_configs[-3]["configurable"]["thread_id"]


def test_customer_id_adds_context_to_the_system_prompt(db_session, seeded_org, monkeypatch):
    org_id, user_id = seeded_org
    customer = customer_controller.create_customer(db_session, org_id, CustomerCreate(name="Ada Obi"))

    captured_kwargs = []
    monkeypatch.setattr(runner, "get_model", lambda: None)
    monkeypatch.setattr(runner, "get_checkpointer", lambda: None)

    def fake_create_agent(**kwargs):
        captured_kwargs.append(kwargs)
        return _FakeAgent([])

    monkeypatch.setattr(runner, "create_agent", fake_create_agent)

    runner.run_chat(db_session, org_id, user_id, "log an order", customer_id=customer.id)
    assert "Ada Obi" in captured_kwargs[-1]["system_prompt"]
    assert str(customer.id) in captured_kwargs[-1]["system_prompt"]

    runner.run_chat(db_session, org_id, user_id, "hello")
    assert "Ada Obi" not in captured_kwargs[-1]["system_prompt"]


def test_business_profile_is_added_to_the_system_prompt(db_session, seeded_org, monkeypatch):
    org_id, user_id = seeded_org

    captured_kwargs = []
    monkeypatch.setattr(runner, "get_model", lambda: None)
    monkeypatch.setattr(runner, "get_checkpointer", lambda: None)
    monkeypatch.setattr(runner, "create_agent", lambda **kwargs: captured_kwargs.append(kwargs) or _FakeAgent([]))

    runner.run_chat(db_session, org_id, user_id, "hello")
    assert "Business profile" not in captured_kwargs[-1]["system_prompt"]

    settings_controller.update_settings(
        db_session, org_id, SettingsUpdate(biz_name="Ada's Fabrics", industry="Tailoring", manager_name="Ada")
    )

    runner.run_chat(db_session, org_id, user_id, "hello")
    prompt = captured_kwargs[-1]["system_prompt"]
    assert "Ada's Fabrics" in prompt
    assert "Tailoring" in prompt
    assert "manager: Ada" in prompt


def test_total_provider_failure_notifies_and_reraises(db_session, seeded_org, monkeypatch):
    org_id, user_id = seeded_org
    monkeypatch.setattr(runner, "get_model", lambda: None)
    monkeypatch.setattr(runner, "get_checkpointer", lambda: None)

    def fake_create_agent(**kwargs):
        class _AlwaysFails:
            def invoke(self, payload, config):
                raise RuntimeError("provider down")

        return _AlwaysFails()

    monkeypatch.setattr(runner, "create_agent", fake_create_agent)

    with pytest.raises(RuntimeError):
        runner.run_chat(db_session, org_id, user_id, "hello")

    notifications = notification_controller.list_notifications(db_session, org_id)
    assert any(n.type == "agent.unavailable" for n in notifications)
