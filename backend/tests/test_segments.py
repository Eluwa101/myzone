import app.routes.segments as segments_routes
from app.agent import segment_suggest
from app.agent.segment_suggest import SegmentSuggestionError, suggest_segment_filters


def _create_customer(client, auth_headers, **kwargs):
    return client.post("/api/customers", json={"name": "Unnamed", **kwargs}, headers=auth_headers).json()


class _FakeResult:
    def __init__(self, content):
        self.content = content


def test_suggest_segment_filters_parses_plain_json(monkeypatch):
    monkeypatch.setattr(segment_suggest, "get_model", lambda: None)
    monkeypatch.setattr(
        segment_suggest,
        "call_with_fallback",
        lambda get_model_fn, invoke: _FakeResult('{"status": "lead", "interest_contains": "Generator"}'),
    )
    filters = suggest_segment_filters("leads interested in generators")
    assert filters.status == "lead"
    assert filters.interest_contains == "Generator"
    assert filters.has_consent is None


def test_suggest_segment_filters_strips_markdown_fences(monkeypatch):
    monkeypatch.setattr(segment_suggest, "get_model", lambda: None)
    monkeypatch.setattr(
        segment_suggest,
        "call_with_fallback",
        lambda get_model_fn, invoke: _FakeResult('```json\n{"last_purchase_over_days": 60}\n```'),
    )
    filters = suggest_segment_filters("haven't bought in 2 months")
    assert filters.last_purchase_over_days == 60


def test_suggest_segment_filters_raises_on_unparseable_output(monkeypatch):
    monkeypatch.setattr(segment_suggest, "get_model", lambda: None)
    monkeypatch.setattr(segment_suggest, "call_with_fallback", lambda get_model_fn, invoke: _FakeResult("not json at all"))
    try:
        suggest_segment_filters("gibberish")
        assert False, "expected SegmentSuggestionError"
    except SegmentSuggestionError:
        pass


def test_suggest_route_returns_parsed_filters(client, auth_headers, monkeypatch):
    from app.schemas.segment import SegmentFilters

    def fake_suggest(description):
        assert description == "leads interested in generators"
        return SegmentFilters(status="lead", interest_contains="Generator")

    monkeypatch.setattr(segments_routes, "suggest_segment_filters", fake_suggest)

    resp = client.post("/api/segments/suggest", json={"description": "leads interested in generators"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "lead"
    assert resp.json()["interest_contains"] == "Generator"


def test_suggest_route_returns_422_when_unparseable(client, auth_headers, monkeypatch):
    def fake_suggest(description):
        raise SegmentSuggestionError("bad output")

    monkeypatch.setattr(segments_routes, "suggest_segment_filters", fake_suggest)

    resp = client.post("/api/segments/suggest", json={"description": "gibberish"}, headers=auth_headers)
    assert resp.status_code == 422


def test_create_and_list_segments(client, auth_headers):
    resp = client.post("/api/segments", json={"name": "Leads", "filters": {"status": "lead"}}, headers=auth_headers)
    assert resp.status_code == 201
    listing = client.get("/api/segments", headers=auth_headers).json()
    assert len(listing) == 1
    assert listing[0]["name"] == "Leads"


def test_segment_members_filters_by_status(client, auth_headers):
    _create_customer(client, auth_headers, name="Ada Obi", status="lead")
    _create_customer(client, auth_headers, name="Bo Chen", status="customer")

    segment = client.post("/api/segments", json={"name": "Leads", "filters": {"status": "lead"}}, headers=auth_headers).json()
    result = client.get(f"/api/segments/{segment['id']}/members", headers=auth_headers).json()
    assert result["total"] == 1
    assert result["members"][0]["name"] == "Ada Obi"


def test_segment_members_filters_by_interest_substring(client, auth_headers):
    _create_customer(client, auth_headers, name="Ada Obi", interests="Generator, Rice")
    _create_customer(client, auth_headers, name="Bo Chen", interests="Shoes")

    segment = client.post(
        "/api/segments", json={"name": "Generator leads", "filters": {"interest_contains": "generator"}}, headers=auth_headers
    ).json()
    result = client.get(f"/api/segments/{segment['id']}/members", headers=auth_headers).json()
    assert result["total"] == 1
    assert result["members"][0]["name"] == "Ada Obi"


def test_segment_members_filters_by_last_purchase_within_days(client, auth_headers):
    recent = _create_customer(client, auth_headers, name="Ada Obi")
    stale = _create_customer(client, auth_headers, name="Bo Chen")
    client.post(
        f"/api/customers/{recent['id']}/transactions",
        json={"date": "2026-11-01", "item": "Rice", "amount": 1000, "currency": "NGN"},
        headers=auth_headers,
    )
    client.post(
        f"/api/customers/{stale['id']}/transactions",
        json={"date": "2026-01-01", "item": "Rice", "amount": 1000, "currency": "NGN"},
        headers=auth_headers,
    )

    segment = client.post(
        "/api/segments", json={"name": "Recent buyers", "filters": {"last_purchase_within_days": 30}}, headers=auth_headers
    ).json()
    result = client.get(f"/api/segments/{segment['id']}/members", headers=auth_headers).json()
    assert {m["name"] for m in result["members"]} == {"Ada Obi"}


def test_segment_members_filters_by_last_purchase_over_days_includes_never_purchased(client, auth_headers):
    never_bought = _create_customer(client, auth_headers, name="Ada Obi")
    recent_buyer = _create_customer(client, auth_headers, name="Bo Chen")
    client.post(
        f"/api/customers/{recent_buyer['id']}/transactions",
        json={"date": "2026-11-01", "item": "Rice", "amount": 1000, "currency": "NGN"},
        headers=auth_headers,
    )

    segment = client.post(
        "/api/segments", json={"name": "Win-back", "filters": {"last_purchase_over_days": 60}}, headers=auth_headers
    ).json()
    result = client.get(f"/api/segments/{segment['id']}/members", headers=auth_headers).json()
    assert {m["name"] for m in result["members"]} == {"Ada Obi"}
    assert never_bought["id"] in [m["id"] for m in result["members"]]


def test_preview_segment_without_saving(client, auth_headers):
    _create_customer(client, auth_headers, name="Ada Obi", status="lead")
    resp = client.post("/api/segments/preview", json={"status": "lead"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["total"] == 1


def test_update_and_delete_segment(client, auth_headers):
    segment = client.post("/api/segments", json={"name": "Leads", "filters": {"status": "lead"}}, headers=auth_headers).json()
    updated = client.patch(f"/api/segments/{segment['id']}", json={"name": "Hot leads"}, headers=auth_headers).json()
    assert updated["name"] == "Hot leads"

    resp = client.delete(f"/api/segments/{segment['id']}", headers=auth_headers)
    assert resp.status_code == 204
    assert client.get("/api/segments", headers=auth_headers).json() == []
