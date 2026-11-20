"""
The read tools (shared with Ask Your Data) and the write tools added for
segments, templates, settings, forms, webhooks, notifications, custom fields
and CSV import. No LLM: tools are invoked directly.
"""
import datetime
from uuid import UUID

import pytest

from app.agent.tools import build_tools
from app.controllers import agent_controller, webhook_controller
from app.models.outbound_message import MessageChannel, MessageStatus, OutboundMessage
from app.models.pending_action import PendingAction

ALL_GROUP = '{"type":"group","combinator":"and","conditions":[]}'
LEADS = '{"type":"group","combinator":"and","conditions":[{"type":"condition","field":"status","operator":"equals","value":"lead"}]}'


@pytest.fixture
def tools(db_session, seeded_org):
    org_id, user_id = seeded_org
    return {t.name: t for t in build_tools(db_session, org_id, user_id)}


@pytest.fixture
def ada(tools):
    return tools["create_customer"].invoke({"name": "Ada Obi", "email": "ada@mail.com", "phone": "08012345678"})


def confirm(db_session, seeded_org, staged):
    org_id, user_id = seeded_org
    return agent_controller.confirm_pending_action(db_session, org_id, user_id, UUID(staged["action_id"]))


# ------------------------------------------------------------------ reads


def test_get_customer_returns_ids_needed_for_updates(tools, ada):
    tx = tools["add_transaction"].invoke({"customer_id": ada["id"], "date": "2026-11-01", "item": "Rice", "amount": 100})
    order = tools["create_order"].invoke({"customer_id": ada["id"], "items": "Generator"})
    full = tools["get_customer"].invoke({"customer_id": ada["id"]})
    assert full["transactions"][0]["id"] == tx["id"]
    assert full["orders"][0]["id"] == order["id"]
    assert tools["get_customer"].invoke({"customer_id": "not-an-id"})["status"] == "error"


def test_list_transactions_newest_first(tools, ada):
    tools["add_transaction"].invoke({"customer_id": ada["id"], "date": "2026-01-01", "item": "Old", "amount": 1})
    tools["add_transaction"].invoke({"customer_id": ada["id"], "date": "2026-06-01", "item": "New", "amount": 2})
    out = tools["list_transactions"].invoke({"customer_id": ada["id"]})
    assert out["total"] == 2
    assert [t["items"][0]["item"] for t in out["transactions"]] == ["New", "Old"]


def test_list_orders_filters_pending_and_overdue(tools, ada):
    today = datetime.date.today()
    late = tools["create_order"].invoke({"customer_id": ada["id"], "items": "Late", "delivery_date": str(today - datetime.timedelta(days=3))})
    tools["create_order"].invoke({"customer_id": ada["id"], "items": "Future", "delivery_date": str(today + datetime.timedelta(days=3))})
    done = tools["create_order"].invoke({"customer_id": ada["id"], "items": "Done"})
    tools["update_order"].invoke({"customer_id": ada["id"], "order_id": done["id"], "delivered": "true"})

    everyone = tools["list_orders"].invoke({})
    assert everyone["total"] == 3
    assert {o["customer"] for o in everyone["orders"]} == {"Ada Obi"}

    pending = tools["list_orders"].invoke({"pending_only": True})
    assert {o["id"] for o in pending["orders"]} != {done["id"]} and done["id"] not in {o["id"] for o in pending["orders"]}

    overdue = tools["list_orders"].invoke({"overdue_only": True})
    assert [o["id"] for o in overdue["orders"]] == [late["id"]]
    assert overdue["orders"][0]["overdue"] is True

    mine = tools["list_orders"].invoke({"customer_id": ada["id"], "pending_only": True, "overdue_only": True})
    assert [o["id"] for o in mine["orders"]] == [late["id"]]


def test_list_messages_and_get_message(db_session, seeded_org, tools, ada):
    org_id, _ = seeded_org
    db_session.add_all([
        OutboundMessage(org_id=org_id, customer_id=UUID(ada["id"]), channel=MessageChannel.email, status=MessageStatus.sent, subject="Sale", body="<p>Big sale on rice</p>"),
        OutboundMessage(org_id=org_id, customer_id=UUID(ada["id"]), channel=MessageChannel.email, status=MessageStatus.skipped, subject="Sale", body="", error="Unsubscribed"),
    ])
    db_session.commit()

    everything = tools["list_messages"].invoke({})
    assert everything["total"] == 2
    skipped = tools["list_messages"].invoke({"status": "skipped"})
    assert [m["error"] for m in skipped["messages"]] == ["Unsubscribed"]
    sent = tools["list_messages"].invoke({"status": "sent", "search": "rice"})["messages"]
    assert sent[0]["preview"] == "Big sale on rice" and sent[0]["customer"] == "Ada Obi"
    assert tools["list_messages"].invoke({"status": "bogus"})["status"] == "error"

    full = tools["get_message"].invoke({"message_id": sent[0]["id"]})
    assert full["body"] == "Big sale on rice"


def test_sales_report_views(tools, ada):
    tools["add_transaction"].invoke({"customer_id": ada["id"], "date": "2026-10-05", "item": "Rice", "amount": 500, "currency": "NGN"})
    tools["add_transaction"].invoke({"customer_id": ada["id"], "date": "2026-11-05", "item": "Rice", "amount": 700, "currency": "NGN"})
    monthly = tools["get_sales_report"].invoke({"view": "monthly"})
    assert [m["month"] for m in monthly["months"]] == ["2026-10", "2026-11"]
    ranged = tools["get_sales_report"].invoke({"view": "monthly", "start_date": "2026-11-01"})
    assert [m["month"] for m in ranged["months"]] == ["2026-11"]
    top = tools["get_sales_report"].invoke({"view": "top_customers"})
    assert top["top_customers"][0]["total"] == 1200
    assert tools["get_sales_report"].invoke({"view": "weekly"})["status"] == "error"
    assert tools["get_sales_report"].invoke({"start_date": "yesterday"})["status"] == "error"


def test_segment_reads_and_preview(tools, ada):
    tools["update_customer"].invoke({"customer_id": ada["id"], "status": "lead"})
    saved = tools["create_segment"].invoke({"name": "Leads", "filters_json": LEADS})
    assert saved["status"] == "created" and saved["members"] == 1

    assert tools["get_segment"].invoke({"segment": "leads"})["filters"]["conditions"][0]["field"] == "status"
    members = tools["list_segment_members"].invoke({"segment": saved["id"]})
    assert members["total"] == 1 and members["members"][0]["name"] == "Ada Obi"

    fields = tools["get_segment_fields"].invoke({})
    assert any(f["key"] == "status" for f in fields["fields"])
    assert tools["preview_segment"].invoke({"filters_json": LEADS})["total"] == 1
    assert tools["preview_segment"].invoke({"filters_json": "{not json"})["status"] == "error"
    assert tools["preview_segment"].invoke({})["status"] == "error"  # needs one definition
    assert "customers" in tools["get_segment_sql_schema"].invoke({})["schema"]
    assert tools["get_segment"].invoke({"segment": "nope"})["status"] == "error"


def test_preview_email_flags_problems(tools, ada):
    ok = tools["preview_email"].invoke({"customer_id": ada["id"], "subject": "Hi {{customer.first_name}}", "body_html": "<p>Hello</p>"})
    assert ok["subject"] == "Hi Ada" and ok["problems"] == []
    bad = tools["preview_email"].invoke({"customer_id": ada["id"], "subject": "Hi", "body_html": "<p>Save [discount]%</p>"})
    assert bad["placeholders"]


def test_get_settings_and_update_settings(tools):
    out = tools["update_settings"].invoke({"biz_name": "Ada's Shop", "default_currency": "ngn", "staff_names": "Bola, Chidi", "industry": "Retail"})
    assert out["status"] == "updated" and set(out["changed"]) == {"biz_name", "default_currency", "staff_names", "industry"}
    s = tools["get_settings"].invoke({})
    assert s["biz_name"] == "Ada's Shop" and s["default_currency"] == "NGN" and s["staff_names"] == ["Bola", "Chidi"]
    # untouched fields stay; sender address is not exposed to the agent at all
    assert "sender_handle" not in s
    assert tools["update_settings"].invoke({"default_currency": "naira"})["status"] == "error"
    assert tools["update_settings"].invoke({"whatsapp_number": "0801"})["status"] == "error"
    assert tools["update_settings"].invoke({})["status"] == "error"


# ----------------------------------------------------------------- writes


def test_segment_create_update_and_duplicate_guard(tools, ada):
    first = tools["create_segment"].invoke({"name": "Everyone", "filters_json": ALL_GROUP})
    assert first["members"] == 1
    assert tools["create_segment"].invoke({"name": "everyone", "filters_json": ALL_GROUP})["status"] == "error"
    assert tools["create_segment"].invoke({"name": "X"})["status"] == "error"  # no definition
    assert tools["create_segment"].invoke({"name": "X", "filters_json": ALL_GROUP, "sql": "select 1"})["status"] == "error"

    renamed = tools["update_segment"].invoke({"segment": "Everyone", "new_name": "All customers", "filters_json": LEADS})
    assert renamed["name"] == "All customers" and renamed["members"] == 0  # Ada is not a lead
    assert tools["update_segment"].invoke({"segment": "All customers"})["status"] == "error"

    sql = tools["create_segment"].invoke({"name": "By SQL", "sql": "SELECT id FROM customers"})
    assert sql["status"] == "created" and sql["members"] == 1
    assert tools["create_segment"].invoke({"name": "Bad SQL", "sql": "DELETE FROM customers"})["status"] == "error"


def test_email_template_create_update_and_validation(tools):
    made = tools["create_email_template"].invoke({"name": "Welcome", "subject": "Hi {{customer.first_name}}", "body_html": "<p>Welcome</p>"})
    assert made["status"] == "created"
    assert tools["create_email_template"].invoke({"name": "welcome", "subject": "s", "body_html": "b"})["status"] == "error"
    assert tools["create_email_template"].invoke({"name": "Promo", "subject": "s", "body_html": "<p>[discount]% off</p>"})["placeholders"]
    assert tools["create_email_template"].invoke({"name": "Broken", "subject": "s", "body_html": "{{nonsense.tag}}"})["status"] == "error"

    updated = tools["update_email_template"].invoke({"template": "Welcome", "body_html": "<p>Welcome aboard</p>"})
    assert updated["status"] == "updated"
    assert "aboard" in tools["get_email_template"].invoke({"template": made["id"]})["body_html"]
    assert tools["update_email_template"].invoke({"template": "Welcome"})["status"] == "error"


def test_form_create_update_list_hides_secrets(tools):
    from tests.test_agent_scope import FORM_FIELDS

    assert tools["create_form"].invoke({"name": "Bad", "fields_json": "[]"})["status"] == "error"  # contact fields required
    assert tools["create_form"].invoke({"name": "Bad", "fields_json": "nope"})["status"] == "error"
    made = tools["create_form"].invoke({"name": "Sign up", "fields_json": FORM_FIELDS})
    assert made["status"] == "created"

    off = tools["update_form"].invoke({"form": "Sign up", "is_active": "false", "new_name": "Newsletter"})
    assert off["is_active"] is False and off["name"] == "Newsletter"
    listed = tools["list_forms"].invoke({})["forms"][0]
    assert listed["signing_enabled"] is False and "webhook_secret" not in listed and listed["submissions"] == 0
    assert tools["list_form_submissions"].invoke({"form": "Newsletter"})["total"] == 0
    assert tools["update_form"].invoke({"form": "Newsletter"})["status"] == "error"


def test_webhook_flow_stages_creation_and_never_exposes_the_secret(db_session, seeded_org, tools, monkeypatch):
    monkeypatch.setattr(webhook_controller, "dispatch_event", lambda *a, **k: None)
    staged = tools["create_webhook"].invoke({"target_url": "https://hooks.example.com/in", "event_types": "order.created, customer.created"})
    assert staged["status"] == "confirm_required"
    assert tools["list_webhooks"].invoke({})["webhooks"] == []  # nothing yet

    result = confirm(db_session, seeded_org, staged)
    assert result["status"] == "created" and "secret" not in result

    listed = tools["list_webhooks"].invoke({})
    assert listed["webhooks"][0]["event_types"] == ["order.created", "customer.created"]
    assert "secret" not in str(listed)

    paused = tools["set_webhook_active"].invoke({"webhook": "https://hooks.example.com/in", "active": False})
    assert paused["is_active"] is False
    assert tools["list_webhook_deliveries"].invoke({"webhook": listed["webhooks"][0]["id"]})["deliveries"] == []

    gone = tools["delete_webhook"].invoke({"webhook": listed["webhooks"][0]["id"]})
    assert gone["status"] == "confirm_required"
    confirm(db_session, seeded_org, gone)
    assert tools["list_webhooks"].invoke({})["webhooks"] == []


def test_create_webhook_rejects_bad_input_without_staging(db_session, tools):
    assert tools["create_webhook"].invoke({"target_url": "http://localhost/x", "event_types": "order.created"})["status"] == "error"
    assert tools["create_webhook"].invoke({"target_url": "https://a.example.com", "event_types": "order.exploded"})["status"] == "error"
    assert tools["create_webhook"].invoke({"target_url": "https://a.example.com", "event_types": ""})["status"] == "error"
    assert db_session.query(PendingAction).count() == 0


def test_notifications_read_mark_and_delete(db_session, seeded_org, tools):
    from app.controllers import notification_controller

    org_id, _ = seeded_org
    notification_controller.create_notification(db_session, org_id, "x", "First")
    notification_controller.create_notification(db_session, org_id, "x", "Second")
    listed = tools["list_notifications"].invoke({})
    assert listed["unread"] == 2

    first = next(n for n in listed["notifications"] if n["title"] == "First")
    assert tools["mark_notifications_read"].invoke({"notification_id": first["id"]})["marked_read"] == 1
    assert tools["list_notifications"].invoke({"unread_only": True})["unread"] == 1
    assert tools["mark_notifications_read"].invoke({})["marked_read"] == 1
    assert tools["mark_notifications_read"].invoke({"notification_id": "bogus"})["status"] == "error"

    staged = tools["delete_notification"].invoke({"notification_id": first["id"]})
    assert staged["status"] == "confirm_required"
    assert len(tools["list_notifications"].invoke({})["notifications"]) == 2
    confirm(db_session, seeded_org, staged)
    assert len(tools["list_notifications"].invoke({})["notifications"]) == 1


def test_custom_field_rename_and_remove(db_session, seeded_org, tools, ada):
    tools["set_customer_custom_field"].invoke({"customer_id": ada["id"], "field_name": "Car", "value": "Camry"})
    assert tools["list_custom_fields"].invoke({})["custom_fields"] == ["Car"]

    renamed = tools["rename_customer_custom_field"].invoke({"customer_id": ada["id"], "old_name": "Car", "new_name": "Vehicle"})
    assert renamed["extra"] == {"Vehicle": "Camry"}
    assert tools["rename_customer_custom_field"].invoke({"customer_id": ada["id"], "old_name": "Car", "new_name": "X"})["status"] == "error"

    staged = tools["remove_customer_custom_field"].invoke({"customer_id": ada["id"], "field_name": "Vehicle"})
    assert staged["status"] == "confirm_required"
    assert tools["get_customer"].invoke({"customer_id": ada["id"]})["extra"] == {"Vehicle": "Camry"}  # still there
    confirm(db_session, seeded_org, staged)
    assert tools["get_customer"].invoke({"customer_id": ada["id"]})["extra"] == {}
    assert tools["remove_customer_custom_field"].invoke({"customer_id": ada["id"], "field_name": "Vehicle"})["status"] == "error"


def test_csv_import_is_staged_then_runs_on_confirm(db_session, seeded_org, tools):
    csv_text = "name,phone,email\nBola Ade,08011111111,bola@mail.com\nChidi Eze,08022222222,chidi@mail.com\n"
    staged = tools["import_customers_csv"].invoke({"csv_text": csv_text})
    assert staged["status"] == "confirm_required"
    assert tools["search_customers"].invoke({})["total"] == 0  # nothing imported yet

    result = confirm(db_session, seeded_org, staged)
    assert result["status"] == "imported" and result["added"] == 2
    assert tools["search_customers"].invoke({})["total"] == 2
    assert tools["import_customers_csv"].invoke({"csv_text": "name"})["status"] == "error"


def test_list_scans_empty(tools):
    assert tools["list_scans"].invoke({})["scans"] == []
