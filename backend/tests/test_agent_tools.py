"""
Unit tests for the agent's tools, bypassing the LLM entirely (no API key
needed, no network calls). These are the safety-critical paths: dedup
conflicts, the confirm-before-destructive-write flow, and audit logging.
"""
from uuid import UUID

import pytest

from app.agent.tools import build_tools
from app.controllers import agent_controller, customer_controller
from app.models.agent_action import AgentAction
from app.models.pending_action import PendingAction


@pytest.fixture
def tools(db_session, seeded_org):
    org_id, user_id = seeded_org
    return {t.name: t for t in build_tools(db_session, org_id, user_id)}


def test_create_customer_tool_creates_and_logs(db_session, seeded_org, tools):
    org_id, user_id = seeded_org
    result = tools["create_customer"].invoke({"name": "Ada Obi", "phone": "08012345678"})
    assert result["action"] == "created"
    assert result["name"] == "Ada Obi"
    assert result["status"] == "customer"  # the customer's own lifecycle status, untouched

    logged = db_session.query(AgentAction).filter(AgentAction.org_id == org_id).all()
    assert len(logged) == 1
    assert logged[0].tool_name == "create_customer"


def test_create_customer_tool_splits_two_word_name(db_session, seeded_org, tools):
    result = tools["create_customer"].invoke({"name": "Ada Obi"})
    assert result["first_name"] == "Ada"
    assert result["last_name"] == "Obi"
    assert result["name"] == "Ada Obi"


def test_create_customer_tool_single_word_name_has_no_last_name(db_session, seeded_org, tools):
    result = tools["create_customer"].invoke({"name": "Madonna"})
    assert result["first_name"] == "Madonna"
    assert result["last_name"] is None
    assert result["name"] == "Madonna"


def test_create_customer_tool_three_word_name_keeps_rest_as_last_name(db_session, seeded_org, tools):
    result = tools["create_customer"].invoke({"name": "Ada Bello Obi"})
    assert result["first_name"] == "Ada"
    assert result["last_name"] == "Bello Obi"


def test_update_customer_tool_renaming_resplits_first_last(db_session, seeded_org, tools):
    created = tools["create_customer"].invoke({"name": "Ada"})
    assert created["last_name"] is None

    updated = tools["update_customer"].invoke({"customer_id": created["id"], "name": "Ada Obi"})
    assert updated["first_name"] == "Ada"
    assert updated["last_name"] == "Obi"

    renamed_single = tools["update_customer"].invoke({"customer_id": created["id"], "name": "Adaeze"})
    assert renamed_single["first_name"] == "Adaeze"
    assert renamed_single["last_name"] is None


def test_create_customer_tool_flags_duplicate_instead_of_creating(db_session, seeded_org, tools):
    org_id, _ = seeded_org
    tools["create_customer"].invoke({"name": "Ada Obi", "phone": "08012345678"})
    result = tools["create_customer"].invoke({"name": "Ada O.", "phone": "+234 801 234 5678"})
    assert result["status"] == "conflict"

    _, total = customer_controller.list_customers(db_session, org_id)
    assert total == 1


def test_create_customer_as_new_bypasses_duplicate_check(db_session, seeded_org, tools):
    org_id, _ = seeded_org
    tools["create_customer"].invoke({"name": "Ada Obi", "phone": "08012345678"})
    result = tools["create_customer_as_new"].invoke({"name": "Ada Obi", "phone": "08012345678"})
    assert result["action"] == "created"

    _, total = customer_controller.list_customers(db_session, org_id)
    assert total == 2


def test_delete_customer_tool_does_not_delete_immediately(db_session, seeded_org, tools):
    org_id, _ = seeded_org
    created = tools["create_customer"].invoke({"name": "Ada Obi"})
    result = tools["delete_customer"].invoke({"customer_id": created["id"]})

    assert result["status"] == "confirm_required"
    assert "action_id" in result

    # still exists - nothing was deleted yet
    customer_controller.get_customer(db_session, org_id, UUID(created["id"]))
    pending = db_session.query(PendingAction).filter(PendingAction.id == UUID(result["action_id"])).first()
    assert pending is not None
    assert pending.tool_name == "delete_customer"


def test_confirming_pending_delete_actually_deletes(db_session, seeded_org, tools):
    org_id, user_id = seeded_org
    created = tools["create_customer"].invoke({"name": "Ada Obi"})
    result = tools["delete_customer"].invoke({"customer_id": created["id"]})

    agent_controller.confirm_pending_action(db_session, org_id, user_id, UUID(result["action_id"]))

    with pytest.raises(customer_controller.CustomerNotFoundError):
        customer_controller.get_customer(db_session, org_id, UUID(created["id"]))

    logged = db_session.query(AgentAction).filter(AgentAction.tool_name == "delete_customer").all()
    assert len(logged) == 1


def test_rejecting_pending_delete_keeps_the_customer(db_session, seeded_org, tools):
    org_id, user_id = seeded_org
    created = tools["create_customer"].invoke({"name": "Ada Obi"})
    result = tools["delete_customer"].invoke({"customer_id": created["id"]})

    agent_controller.reject_pending_action(db_session, org_id, UUID(result["action_id"]))

    customer_controller.get_customer(db_session, org_id, UUID(created["id"]))  # does not raise
    assert db_session.query(PendingAction).count() == 0


def test_merge_customers_tool_requires_confirmation(db_session, seeded_org, tools):
    org_id, user_id = seeded_org
    a = tools["create_customer"].invoke({"name": "Ada Obi", "email": "ada@mail.com"})
    b = tools["create_customer_as_new"].invoke({"name": "Ada Obi", "email": "ada@mail.com", "pet": "Dog - Max"})

    result = tools["merge_customers"].invoke({"keep_id": a["id"], "merge_id": b["id"]})
    assert result["status"] == "confirm_required"

    # both still exist until confirmed
    customer_controller.get_customer(db_session, org_id, UUID(a["id"]))
    customer_controller.get_customer(db_session, org_id, UUID(b["id"]))

    confirmed = agent_controller.confirm_pending_action(db_session, org_id, user_id, UUID(result["action_id"]))
    assert confirmed["status"] == "merged"
    with pytest.raises(customer_controller.CustomerNotFoundError):
        customer_controller.get_customer(db_session, org_id, UUID(b["id"]))


def test_add_transaction_then_dashboard_summary_reflects_it(db_session, seeded_org, tools):
    created = tools["create_customer"].invoke({"name": "Ada Obi"})
    tools["add_transaction"].invoke({"customer_id": created["id"], "date": "2026-11-01", "item": "Rice", "amount": 15000, "qty": 2, "currency": "ngn"})

    summary = tools["get_dashboard_summary"].invoke({})
    assert summary["all_time_by_currency"]["NGN"] == 15000


def test_add_transaction_with_items_json_creates_one_multi_item_transaction(db_session, seeded_org, tools):
    created = tools["create_customer"].invoke({"name": "Ada Obi"})
    tx = tools["add_transaction"].invoke(
        {
            "customer_id": created["id"],
            "date": "2026-11-01",
            "items_json": '[{"item": "Rice", "qty": 2, "amount": 5000}, {"item": "Sugar", "qty": 1, "amount": 1200}]',
        }
    )
    assert tx["status"] == "created"
    assert tx["amount"] == 6200
    assert len(tx["items"]) == 2

    summary = tools["get_dashboard_summary"].invoke({})
    # currency fell back to the org's configured default (empty in this
    # fixture org, so the all_time bucket key is "")
    assert sum(summary["all_time_by_currency"].values()) == 6200


def test_add_transaction_falls_back_to_org_default_currency(db_session, seeded_org, tools):
    from app.controllers import settings_controller
    from app.schemas.settings import SettingsUpdate

    org_id, _user_id = seeded_org
    settings_controller.update_settings(db_session, org_id, SettingsUpdate(default_currency="NGN"))

    created = tools["create_customer"].invoke({"name": "Ada Obi"})
    tx = tools["add_transaction"].invoke({"customer_id": created["id"], "date": "2026-11-01", "item": "Rice", "amount": 5000})
    assert tx["currency"] == "NGN"


def test_search_customers_tool(db_session, seeded_org, tools):
    tools["create_customer"].invoke({"name": "Ada Obi", "interests": "Generator"})
    tools["create_customer_as_new"].invoke({"name": "Bo Chen"})

    result = tools["search_customers"].invoke({"query": "generator"})
    assert result["total"] == 1
    assert result["customers"][0]["name"] == "Ada Obi"
    assert result["customers"][0]["display_id"] == "CR001"


def test_search_customers_tool_matches_display_id(db_session, seeded_org, tools):
    created = tools["create_customer"].invoke({"name": "Ada Obi"})
    tools["create_customer_as_new"].invoke({"name": "Bo Chen"})

    result = tools["search_customers"].invoke({"query": created["display_id"]})
    assert result["total"] == 1
    assert result["customers"][0]["name"] == "Ada Obi"


def test_find_customer_by_id_tool(db_session, seeded_org, tools):
    created = tools["create_customer"].invoke({"name": "Ada Obi"})

    found = tools["find_customer_by_id"].invoke({"display_id": created["display_id"]})
    assert found["action"] == "found"
    assert found["name"] == "Ada Obi"


def test_find_customer_by_id_tool_unknown_id(db_session, seeded_org, tools):
    result = tools["find_customer_by_id"].invoke({"display_id": "CR999"})
    assert result["status"] == "error"


def test_update_transaction_tool_then_delete_tool(db_session, seeded_org, tools):
    created = tools["create_customer"].invoke({"name": "Ada Obi"})
    tx = tools["add_transaction"].invoke({"customer_id": created["id"], "date": "2026-11-01", "item": "Rice", "amount": 15000})

    updated = tools["update_transaction"].invoke({"customer_id": created["id"], "transaction_id": tx["id"], "amount": 20000})
    assert updated["status"] == "updated"
    assert updated["amount"] == 20000

    deleted = tools["delete_transaction"].invoke({"customer_id": created["id"], "transaction_id": tx["id"]})
    assert deleted["status"] == "deleted"

    summary = tools["get_dashboard_summary"].invoke({})
    assert summary["all_time_by_currency"] == {}


def test_update_order_tool_sets_delivery_date_and_marks_delivered(db_session, seeded_org, tools):
    created = tools["create_customer"].invoke({"name": "Ada Obi"})
    order = tools["create_order"].invoke({"customer_id": created["id"], "items": "2 generators"})
    assert order["delivery_date"] is None

    updated = tools["update_order"].invoke({"customer_id": created["id"], "order_id": order["id"], "delivery_date": "2026-12-01", "delivered": "true"})
    assert updated["status"] == "updated"
    assert updated["delivery_date"] == "2026-12-01"
    assert updated["delivered"] is True


def test_delete_order_tool(db_session, seeded_org, tools):
    created = tools["create_customer"].invoke({"name": "Ada Obi"})
    order = tools["create_order"].invoke({"customer_id": created["id"], "items": "Generator"})

    result = tools["delete_order"].invoke({"customer_id": created["id"], "order_id": order["id"]})
    assert result["status"] == "deleted"

    listing = tools["search_customers"].invoke({"query": "Ada"})
    assert listing["total"] == 1  # the customer itself is untouched


def test_list_notes_update_note_delete_note_tools(db_session, seeded_org, tools):
    created = tools["create_customer"].invoke({"name": "Ada Obi"})
    note = tools["add_customer_note"].invoke({"customer_id": created["id"], "title": "Flag", "content": "Owes for last month"})
    assert note["status"] == "pending_review"

    listed = tools["list_notes"].invoke({"customer_id": created["id"]})
    assert len(listed["notes"]) == 1
    assert listed["notes"][0]["id"] == note["id"]
    assert listed["notes"][0]["pending_review"] is True

    reviewed = tools["update_note"].invoke({"note_id": note["id"], "content": "Paid up now", "mark_reviewed": "true"})
    assert reviewed["status"] == "updated"
    assert reviewed["content"] == "Paid up now"
    assert reviewed["is_pending_review"] is False

    deleted = tools["delete_note"].invoke({"note_id": note["id"]})
    assert deleted["status"] == "deleted"
    assert tools["list_notes"].invoke({})["notes"] == []
