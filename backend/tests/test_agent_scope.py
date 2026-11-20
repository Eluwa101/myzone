"""
The split between the two assistants, and the rule that every delete is
destructive:

- Ask Your Data is handed only read-only tools - structurally unable to write.
- The chat assistant has read + write tools, but every delete/removal (and
  merge, send, new webhook, CSV import) is staged as a PendingAction that a
  human confirms; nothing changes before that.
"""
import re
from uuid import UUID

import pytest

import app.agent.ask_data as ask_data_module
from app.agent.read_tools import build_read_tools
from app.agent.tools import build_tools
from app.controllers import agent_controller
from app.models.pending_action import PendingAction

WRITE_PREFIXES = ("create_", "update_", "delete_", "add_", "set_", "remove_", "merge_", "send_", "import_", "rename_", "mark_")


@pytest.fixture
def org(db_session, seeded_org):
    return seeded_org


def test_read_tools_contain_no_write_verbs(db_session, org):
    org_id, _ = org
    names = [t.name for t in build_read_tools(db_session, org_id)]
    assert names, "read tool set must not be empty"
    assert not [n for n in names if n.startswith(WRITE_PREFIXES)]


def test_read_tools_cannot_even_be_built_with_a_user(db_session, org):
    # no user_id parameter at all - so no read tool can log an action or stage a pending one
    org_id, user_id = org
    with pytest.raises(TypeError):
        build_read_tools(db_session, org_id, user_id)


def test_ask_data_is_given_only_read_tools(db_session, org, monkeypatch):
    org_id, _ = org
    seen = {}

    class _Msg:
        content = "answer"

    class _Agent:
        def invoke(self, *_a, **_k):
            return {"messages": [_Msg()]}

    def fake_create_agent(model, tools, system_prompt, **kw):
        seen["tools"] = [t.name for t in tools]
        seen["kwargs"] = kw
        return _Agent()

    monkeypatch.setattr(ask_data_module, "create_agent", fake_create_agent)
    monkeypatch.setattr(ask_data_module, "call_with_fallback", lambda get_model, fn: fn(object()))

    assert ask_data_module.ask_data(db_session, org_id, "who owes me?") == "answer"
    read_names = {t.name for t in build_read_tools(db_session, org_id)}
    assert set(seen["tools"]) == read_names
    assert not [n for n in seen["tools"] if n.startswith(WRITE_PREFIXES)]
    assert "checkpointer" not in seen["kwargs"]  # nothing persisted either


def test_chat_has_every_read_tool_plus_writes(db_session, org):
    org_id, user_id = org
    chat = {t.name for t in build_tools(db_session, org_id, user_id)}
    reads = {t.name for t in build_read_tools(db_session, org_id)}
    assert reads <= chat
    assert {"create_segment", "update_settings", "create_form", "delete_order"} <= chat


def test_every_delete_or_removal_tool_has_a_confirm_executor(db_session, org):
    org_id, user_id = org
    for t in build_tools(db_session, org_id, user_id):
        if t.name.startswith(("delete_", "remove_")):
            assert t.name in agent_controller._EXECUTORS, f"{t.name} would stage an action nothing can execute"


def _make_everything(tools):
    """One of each deletable thing; returns {tool_name: args} for its delete tool."""
    ada = tools["create_customer"].invoke({"name": "Ada Obi", "email": "ada@mail.com"})
    tx = tools["add_transaction"].invoke({"customer_id": ada["id"], "date": "2026-11-01", "item": "Rice", "amount": 100})
    order = tools["create_order"].invoke({"customer_id": ada["id"], "items": "Rice"})
    note = tools["create_shared_note"].invoke({"customer_ids": ada["id"], "title": "T", "content": "C"})
    tools["set_customer_custom_field"].invoke({"customer_id": ada["id"], "field_name": "Car", "value": "Camry"})
    seg = tools["create_segment"].invoke({"name": "All", "filters_json": '{"type":"group","combinator":"and","conditions":[]}'})
    tpl = tools["create_email_template"].invoke({"name": "Hi", "subject": "Hello", "body_html": "<p>Hi {{customer.first_name}}</p>"})
    form = tools["create_form"].invoke({"name": "Sign up", "fields_json": FORM_FIELDS})
    return {
        "delete_customer": {"customer_id": ada["id"]},
        "delete_transaction": {"customer_id": ada["id"], "transaction_id": tx["id"]},
        "delete_order": {"customer_id": ada["id"], "order_id": order["id"]},
        "delete_note": {"note_id": note["id"]},
        "remove_customer_custom_field": {"customer_id": ada["id"], "field_name": "Car"},
        "delete_segment": {"segment": seg["id"]},
        "delete_email_template": {"template": tpl["id"]},
        "delete_form": {"form": form["id"]},
    }


FORM_FIELDS = (
    '[{"key":"first_name","label":"First name","type":"text","required":true,"category":"customer"},'
    '{"key":"last_name","label":"Last name","category":"customer"},'
    '{"key":"phone","label":"Phone","type":"tel","category":"customer"},'
    '{"key":"email","label":"Email","type":"email","category":"customer"}]'
)


def test_every_delete_is_staged_and_nothing_is_removed_until_confirmed(db_session, org):
    org_id, user_id = org
    tools = {t.name: t for t in build_tools(db_session, org_id, user_id)}
    calls = _make_everything(tools)

    def snapshot():
        ada = tools["search_customers"].invoke({"query": "Ada"})["customers"]
        return (
            len(ada),
            len(tools["list_segments"].invoke({})["segments"]),
            len(tools["list_email_templates"].invoke({})["templates"]),
            len(tools["list_forms"].invoke({})["forms"]),
        )

    before = snapshot()
    staged = {}
    for name, args in calls.items():
        result = tools[name].invoke(args)
        assert result["status"] == "confirm_required", f"{name} acted immediately"
        staged[name] = result["action_id"]

    assert snapshot() == before  # nothing happened yet
    assert db_session.query(PendingAction).count() == len(calls)

    # confirm the dependent ones first, the customer last
    for name in [n for n in calls if n != "delete_customer"] + ["delete_customer"]:
        out = agent_controller.confirm_pending_action(db_session, org_id, user_id, UUID(staged[name]))
        assert out["status"] in ("deleted", "removed"), (name, out)

    assert snapshot() == (0, 0, 0, 0)


def test_confirming_an_action_whose_target_vanished_reports_instead_of_crashing(db_session, org):
    org_id, user_id = org
    tools = {t.name: t for t in build_tools(db_session, org_id, user_id)}
    note = tools["create_shared_note"].invoke({"customer_ids": tools["create_customer"].invoke({"name": "Ada"})["id"], "title": "T", "content": "C"})
    staged = tools["delete_note"].invoke({"note_id": note["id"]})
    # deleted some other way in the meantime
    from app.controllers import note_controller

    note_controller.delete_note(db_session, org_id, UUID(note["id"]))

    out = agent_controller.confirm_pending_action(db_session, org_id, user_id, UUID(staged["action_id"]))
    assert out["status"] == "error"
    assert db_session.query(PendingAction).count() == 0  # stale request cleared, not retried forever


def test_delete_tools_reject_unknown_ids_without_staging(db_session, org):
    org_id, user_id = org
    tools = {t.name: t for t in build_tools(db_session, org_id, user_id)}
    zero = str(UUID(int=0))
    assert tools["delete_note"].invoke({"note_id": zero})["status"] == "error"
    assert tools["delete_segment"].invoke({"segment": "nope"})["status"] == "error"
    assert tools["delete_order"].invoke({"customer_id": zero, "order_id": zero})["status"] == "error"
    assert db_session.query(PendingAction).count() == 0


def test_staged_action_descriptions_say_what_will_be_deleted(db_session, org):
    org_id, user_id = org
    tools = {t.name: t for t in build_tools(db_session, org_id, user_id)}
    calls = _make_everything(tools)
    desc = tools["delete_segment"].invoke(calls["delete_segment"])
    pending = db_session.query(PendingAction).filter(PendingAction.id == UUID(desc["action_id"])).one()
    assert "All" in pending.description
    assert not re.search(r"[0-9a-f]{8}-[0-9a-f]{4}", pending.description)  # readable, not raw ids
