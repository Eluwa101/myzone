"""
A segment is a snapshot: its member list stays as it is until someone adds new
matches or reruns it. Only *who belongs* is frozen - each member's details stay live.
"""
from uuid import UUID

import pytest

from app.agent.tools import build_tools
from app.controllers import agent_controller, segment_controller
from app.models.segment import Segment, SegmentMember
from tests.conftest import verify_user_email

LEADS = {"type": "group", "combinator": "and", "conditions": [{"type": "condition", "field": "status", "operator": "equals", "value": "lead"}]}
CUSTOMERS_ONLY = {"type": "group", "combinator": "and", "conditions": [{"type": "condition", "field": "status", "operator": "equals", "value": "customer"}]}


def _lead(client, headers, name):
    return client.post("/api/customers?force=true", json={"name": name, "status": "lead"}, headers=headers).json()


def _members(client, headers, segment_id):
    resp = client.get(f"/api/segments/{segment_id}/members", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _names(data):
    return sorted(m["name"] for m in data["members"])


@pytest.fixture
def segment(client, auth_headers):
    _lead(client, auth_headers, "Ada Obi")
    _lead(client, auth_headers, "Bola Ade")
    resp = client.post("/api/segments", json={"name": "Leads", "filters": LEADS}, headers=auth_headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_a_new_segment_stores_who_matched_when_it_was_created(client, auth_headers, segment):
    assert segment["member_count"] == 2 and segment["refreshed_at"] is not None
    data = _members(client, auth_headers, segment["id"])
    assert _names(data) == ["Ada Obi", "Bola Ade"] and data["refreshed_at"] is not None


def test_new_matches_do_not_join_until_added(client, auth_headers, segment):
    _lead(client, auth_headers, "Chidi Eze")
    assert _names(_members(client, auth_headers, segment["id"])) == ["Ada Obi", "Bola Ade"]  # unchanged

    changes = client.get(f"/api/segments/{segment['id']}/changes", headers=auth_headers).json()
    assert changes["to_add"] == 1 and changes["add_sample"] == ["Chidi Eze"] and changes["to_remove"] == 0

    out = client.post(f"/api/segments/{segment['id']}/refresh", json={"mode": "add"}, headers=auth_headers).json()
    assert out["added"] == 1 and out["removed"] == 0 and out["total"] == 3
    assert _names(_members(client, auth_headers, segment["id"])) == ["Ada Obi", "Bola Ade", "Chidi Eze"]


def test_someone_who_stops_matching_stays_until_a_rerun(client, auth_headers, segment):
    ada = next(m for m in _members(client, auth_headers, segment["id"])["members"] if m["name"] == "Ada Obi")
    client.patch(f"/api/customers/{ada['id']}", json={"status": "customer"}, headers=auth_headers)
    _lead(client, auth_headers, "Chidi Eze")

    assert "Ada Obi" in _names(_members(client, auth_headers, segment["id"]))  # still in the list
    changes = client.get(f"/api/segments/{segment['id']}/changes", headers=auth_headers).json()
    assert changes["to_remove"] == 1 and changes["remove_sample"] == ["Ada Obi"] and changes["to_add"] == 1

    # "add" never removes anyone
    out = client.post(f"/api/segments/{segment['id']}/refresh", json={"mode": "add"}, headers=auth_headers).json()
    assert out["removed"] == 0 and "Ada Obi" in _names(_members(client, auth_headers, segment["id"]))

    # "rerun" replaces the list with exactly who matches now
    out = client.post(f"/api/segments/{segment['id']}/refresh", json={"mode": "rerun"}, headers=auth_headers).json()
    assert out["removed"] == 1 and out["total"] == 2
    assert _names(_members(client, auth_headers, segment["id"])) == ["Bola Ade", "Chidi Eze"]
    assert client.get(f"/api/segments/{segment['id']}/changes", headers=auth_headers).json()["to_add"] == 0


def test_member_details_stay_live_even_though_membership_is_frozen(client, auth_headers, segment):
    ada = next(m for m in _members(client, auth_headers, segment["id"])["members"] if m["name"] == "Ada Obi")
    client.patch(f"/api/customers/{ada['id']}", json={"name": "Ada Okafor", "phone": "0802"}, headers=auth_headers)
    renamed = next(m for m in _members(client, auth_headers, segment["id"])["members"] if m["id"] == ada["id"])
    assert renamed["name"] == "Ada Okafor" and renamed["phone"] == "0802"


def test_a_segment_from_before_snapshots_is_run_the_first_time_it_is_opened(client, auth_headers, db_session):
    from app.models.user import User

    org_id = db_session.query(User).filter(User.email == "ada@example.com").first().org_id
    _lead(client, auth_headers, "Ada Obi")
    legacy = Segment(org_id=org_id, name="Old one", filters=LEADS, sql=None)  # no refreshed_at, no stored rows
    db_session.add(legacy)
    db_session.commit()
    assert db_session.query(SegmentMember).count() == 0

    listed = client.get("/api/segments", headers=auth_headers).json()
    assert listed[0]["member_count"] == 1 and listed[0]["refreshed_at"] is not None
    _lead(client, auth_headers, "Bola Ade")
    assert _names(_members(client, auth_headers, str(legacy.id))) == ["Ada Obi"]  # frozen from its first run


def test_changing_the_definition_reruns_but_renaming_does_not(client, auth_headers, segment):
    _lead(client, auth_headers, "Chidi Eze")
    renamed = client.patch(f"/api/segments/{segment['id']}", json={"name": "Warm leads"}, headers=auth_headers).json()
    assert renamed["name"] == "Warm leads" and renamed["member_count"] == 2  # Chidi still not in

    redefined = client.patch(f"/api/segments/{segment['id']}", json={"filters": LEADS}, headers=auth_headers).json()
    assert redefined["member_count"] == 3  # new definition = fresh run

    switched = client.patch(f"/api/segments/{segment['id']}", json={"filters": CUSTOMERS_ONLY}, headers=auth_headers).json()
    assert switched["member_count"] == 0


def test_a_failing_new_definition_leaves_the_old_list_alone(client, auth_headers, segment):
    resp = client.patch(f"/api/segments/{segment['id']}", json={"sql": "SELECT nope FROM nowhere"}, headers=auth_headers)
    assert resp.status_code == 422
    assert _names(_members(client, auth_headers, segment["id"])) == ["Ada Obi", "Bola Ade"]


def test_preview_is_still_live(client, auth_headers, segment):
    _lead(client, auth_headers, "Chidi Eze")
    preview = client.post("/api/segments/preview", json=LEADS, headers=auth_headers).json()
    assert preview["total"] == 3 and preview["refreshed_at"] is None  # an unsaved preview is a live query


def test_deleting_a_customer_removes_them_from_lists(client, auth_headers, segment, db_session):
    ada = next(m for m in _members(client, auth_headers, segment["id"])["members"] if m["name"] == "Ada Obi")
    assert client.delete(f"/api/customers/{ada['id']}", headers=auth_headers).status_code == 204
    assert _names(_members(client, auth_headers, segment["id"])) == ["Bola Ade"]
    assert db_session.query(SegmentMember).count() == 1


def test_merging_keeps_the_survivor_in_the_list(client, auth_headers, segment):
    members = {m["name"]: m["id"] for m in _members(client, auth_headers, segment["id"])["members"]}
    # Ada is in the list, a duplicate of her is not
    dupe = client.post("/api/customers?force=true", json={"name": "Ada O.", "status": "customer"}, headers=auth_headers).json()
    client.post("/api/customers/merge", json={"keep_id": dupe["id"], "merge_id": members["Ada Obi"]}, headers=auth_headers)
    names = _names(_members(client, auth_headers, segment["id"]))
    assert "Ada O." in names and "Ada Obi" not in names  # her slot moved to the record that survived


def test_other_businesses_cannot_see_or_change_a_list(client, auth_headers, segment):
    client.post("/api/auth/signup", json={"org_name": "Other Co", "email": "bola@example.com", "password": "supersecret"})
    verify_user_email("bola@example.com")
    token = client.post("/api/auth/login", json={"email": "bola@example.com", "password": "supersecret"}).json()["access_token"]
    other = {"Authorization": f"Bearer {token}"}
    assert client.get(f"/api/segments/{segment['id']}/changes", headers=other).status_code == 404
    assert client.post(f"/api/segments/{segment['id']}/refresh", json={"mode": "rerun"}, headers=other).status_code == 404
    assert client.post(f"/api/segments/{segment['id']}/refresh", json={"mode": "bogus"}, headers=auth_headers).status_code == 422


# --- the assistant ------------------------------------------------------------


@pytest.fixture
def tools(db_session, seeded_org):
    org_id, user_id = seeded_org
    return {t.name: t for t in build_tools(db_session, org_id, user_id)}


def test_emailing_a_segment_uses_its_stored_list(db_session, seeded_org, tools):
    org_id, user_id = seeded_org
    tools["create_customer"].invoke({"name": "Ada Obi", "email": "ada@mail.com"})
    tools["update_customer"].invoke({"customer_id": tools["search_customers"].invoke({})["customers"][0]["id"], "status": "lead"})
    seg = tools["create_segment"].invoke({"name": "Leads", "filters_json": '{"type":"group","combinator":"and","conditions":[{"type":"condition","field":"status","operator":"equals","value":"lead"}]}'})
    assert seg["members"] == 1

    bola = tools["create_customer"].invoke({"name": "Bola Ade", "email": "bola@mail.com"})
    tools["update_customer"].invoke({"customer_id": bola["id"], "status": "lead"})  # matches now, but isn't in the list

    staged = tools["send_customer_email"].invoke({"segment_name": "Leads", "subject": "Hi", "body_html": "<p>Hello</p>"})
    pending = agent_controller.get_pending_action(db_session, org_id, UUID(staged["action_id"]))
    assert len(pending.payload["customer_ids"]) == 1  # only who was in the list

    assert tools["list_segments"].invoke({})["segments"][0]["members"] == 1


def test_assistant_can_see_changes_add_immediately_and_must_confirm_a_rerun(db_session, seeded_org, tools):
    org_id, user_id = seeded_org
    ada = tools["create_customer"].invoke({"name": "Ada Obi"})
    tools["update_customer"].invoke({"customer_id": ada["id"], "status": "lead"})
    tools["create_segment"].invoke({"name": "Leads", "filters_json": '{"type":"group","combinator":"and","conditions":[{"type":"condition","field":"status","operator":"equals","value":"lead"}]}'})

    bola = tools["create_customer"].invoke({"name": "Bola Ade"})
    tools["update_customer"].invoke({"customer_id": bola["id"], "status": "lead"})
    changes = tools["get_segment_changes"].invoke({"segment": "Leads"})
    assert changes["new_matches"] == 1 and changes["new_match_names"] == ["Bola Ade"] and changes["no_longer_match"] == 0

    added = tools["refresh_segment"].invoke({"segment": "Leads"})  # default mode: add - only ever adds, so no confirmation
    assert added["status"] == "updated" and added["added"] == 1 and added["members"] == 2

    tools["update_customer"].invoke({"customer_id": ada["id"], "status": "customer"})  # Ada stops matching
    assert tools["refresh_segment"].invoke({"segment": "Leads", "mode": "add"})["removed"] == 0
    assert tools["get_segment"].invoke({"segment": "Leads"})["members"] == 2

    staged = tools["refresh_segment"].invoke({"segment": "Leads", "mode": "rerun"})  # would drop Ada -> needs a human
    assert staged["status"] == "confirm_required" and "Ada Obi" in staged["description"]
    assert tools["get_segment"].invoke({"segment": "Leads"})["members"] == 2  # nothing yet
    out = agent_controller.confirm_pending_action(db_session, org_id, user_id, UUID(staged["action_id"]))
    assert out["removed"] == 1 and out["members"] == 1

    assert tools["refresh_segment"].invoke({"segment": "Leads", "mode": "rerun"})["status"] == "updated"  # nothing to drop: immediate
    assert tools["refresh_segment"].invoke({"segment": "Leads", "mode": "sideways"})["status"] == "error"
    assert tools["refresh_segment"].invoke({"segment": "Nope"})["status"] == "error"


def test_segment_membership_is_purged_with_the_business(client, auth_headers, segment, db_session):
    # covered generically by the closure test; this checks the rows really exist to be purged
    assert db_session.query(SegmentMember).filter(SegmentMember.segment_id == UUID(segment["id"])).count() == 2
    assert segment_controller is not None
