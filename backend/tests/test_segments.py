import app.routes.segments as segments_routes
from app.agent import segment_suggest
from app.agent.segment_suggest import SegmentSuggestionError, suggest_segment_filters


def _create_customer(client, auth_headers, **kwargs):
    return client.post("/api/customers", json={"name": "Unnamed", **kwargs}, headers=auth_headers).json()


def cond(field, operator, value=None, value2=None, values=None):
    c = {"type": "condition", "field": field, "operator": operator}
    if value is not None:
        c["value"] = value
    if value2 is not None:
        c["value2"] = value2
    if values is not None:
        c["values"] = values
    return c


def group(combinator, conditions):
    return {"type": "group", "combinator": combinator, "conditions": conditions}


class _FakeResult:
    def __init__(self, content):
        self.content = content


def test_suggest_segment_filters_parses_plain_json(monkeypatch):
    monkeypatch.setattr(segment_suggest, "get_model", lambda: None)
    monkeypatch.setattr(
        segment_suggest,
        "call_with_fallback",
        lambda get_model_fn, invoke: _FakeResult(
            '{"type": "group", "combinator": "and", "conditions": ['
            '{"type": "condition", "field": "status", "operator": "equals", "value": "lead"}]}'
        ),
    )
    filters = suggest_segment_filters("leads")
    assert filters.combinator == "and"
    assert filters.conditions[0].field == "status"
    assert filters.conditions[0].value == "lead"


def test_suggest_segment_filters_strips_markdown_fences(monkeypatch):
    monkeypatch.setattr(segment_suggest, "get_model", lambda: None)
    monkeypatch.setattr(
        segment_suggest,
        "call_with_fallback",
        lambda get_model_fn, invoke: _FakeResult(
            '```json\n{"type": "group", "conditions": ['
            '{"type": "condition", "field": "last_purchase_date", "operator": "over_days_ago", "value": 60}]}\n```'
        ),
    )
    filters = suggest_segment_filters("haven't bought in 2 months")
    assert filters.conditions[0].operator == "over_days_ago"
    assert filters.conditions[0].value == 60


def test_suggest_segment_filters_defaults_missing_type_to_group(monkeypatch):
    monkeypatch.setattr(segment_suggest, "get_model", lambda: None)
    monkeypatch.setattr(segment_suggest, "call_with_fallback", lambda get_model_fn, invoke: _FakeResult('{"conditions": []}'))
    filters = suggest_segment_filters("everyone")
    assert filters.type == "group"
    assert filters.conditions == []


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
        return SegmentFilters.model_validate(
            group("and", [cond("status", "equals", "lead"), cond("interests", "contains", "Generator")])
        )

    monkeypatch.setattr(segments_routes, "suggest_segment_filters", fake_suggest)

    resp = client.post("/api/segments/suggest", json={"description": "leads interested in generators"}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["combinator"] == "and"
    assert len(body["conditions"]) == 2


def test_suggest_route_returns_422_when_unparseable(client, auth_headers, monkeypatch):
    def fake_suggest(description):
        raise SegmentSuggestionError("bad output")

    monkeypatch.setattr(segments_routes, "suggest_segment_filters", fake_suggest)

    resp = client.post("/api/segments/suggest", json={"description": "gibberish"}, headers=auth_headers)
    assert resp.status_code == 422


def test_fields_endpoint_lists_fields_operators_and_custom_fields(client, auth_headers):
    _create_customer(client, auth_headers, name="Ada Obi", extra={"Car": "Camry"})
    resp = client.get("/api/segments/fields", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    keys = {f["key"] for f in body["fields"]}
    assert {"status", "total_spent", "has_unpaid_order", "last_purchase_date"} <= keys
    assert "between" in body["operators_by_type"]["number"]
    assert body["custom_fields"] == ["Car"]


def test_create_and_list_segments(client, auth_headers):
    resp = client.post("/api/segments", json={"name": "Leads", "filters": group("and", [cond("status", "equals", "lead")])}, headers=auth_headers)
    assert resp.status_code == 201
    listing = client.get("/api/segments", headers=auth_headers).json()
    assert len(listing) == 1
    assert listing[0]["name"] == "Leads"


def test_segment_members_filters_by_status(client, auth_headers):
    _create_customer(client, auth_headers, name="Ada Obi", status="lead")
    _create_customer(client, auth_headers, name="Bo Chen", status="customer")

    segment = client.post(
        "/api/segments", json={"name": "Leads", "filters": group("and", [cond("status", "equals", "lead")])}, headers=auth_headers
    ).json()
    result = client.get(f"/api/segments/{segment['id']}/members", headers=auth_headers).json()
    assert result["total"] == 1
    assert result["members"][0]["name"] == "Ada Obi"


def test_segment_members_not_equals(client, auth_headers):
    _create_customer(client, auth_headers, name="Ada Obi", status="lead")
    _create_customer(client, auth_headers, name="Bo Chen", status="customer")

    resp = client.post("/api/segments/preview", json=group("and", [cond("status", "not_equals", "lead")]), headers=auth_headers)
    assert {m["name"] for m in resp.json()["members"]} == {"Bo Chen"}


def test_segment_members_in_list_and_not_in_list(client, auth_headers):
    ada = _create_customer(client, auth_headers, name="Ada Obi", status="lead")
    bo = _create_customer(client, auth_headers, name="Bo Chen", status="customer")
    _create_customer(client, auth_headers, name="Chi Eze", status="inactive")

    in_resp = client.post(
        "/api/segments/preview", json=group("and", [cond("status", "in_list", values=["lead", "customer"])]), headers=auth_headers
    )
    assert {m["id"] for m in in_resp.json()["members"]} == {ada["id"], bo["id"]}

    not_in_resp = client.post(
        "/api/segments/preview", json=group("and", [cond("status", "not_in_list", values=["lead", "customer"])]), headers=auth_headers
    )
    assert {m["name"] for m in not_in_resp.json()["members"]} == {"Chi Eze"}


def test_segment_members_contains_and_is_set(client, auth_headers):
    _create_customer(client, auth_headers, name="Ada Obi", interests="Generator, Rice")
    _create_customer(client, auth_headers, name="Bo Chen", interests="Shoes")
    _create_customer(client, auth_headers, name="Chi Eze")

    contains_resp = client.post(
        "/api/segments/preview", json=group("and", [cond("interests", "contains", "generator")]), headers=auth_headers
    )
    assert {m["name"] for m in contains_resp.json()["members"]} == {"Ada Obi"}

    is_set_resp = client.post("/api/segments/preview", json=group("and", [cond("interests", "is_set")]), headers=auth_headers)
    assert {m["name"] for m in is_set_resp.json()["members"]} == {"Ada Obi", "Bo Chen"}

    is_not_set_resp = client.post("/api/segments/preview", json=group("and", [cond("interests", "is_not_set")]), headers=auth_headers)
    assert {m["name"] for m in is_not_set_resp.json()["members"]} == {"Chi Eze"}


def test_segment_members_between_on_total_spent(client, auth_headers):
    low = _create_customer(client, auth_headers, name="Ada Obi")
    mid = _create_customer(client, auth_headers, name="Bo Chen")
    high = _create_customer(client, auth_headers, name="Chi Eze")
    for cust, amount in [(low, 1000), (mid, 5000), (high, 50000)]:
        client.post(
            f"/api/customers/{cust['id']}/transactions",
            json={"date": "2026-11-01", "item": "Item", "amount": amount, "currency": "NGN"},
            headers=auth_headers,
        )

    resp = client.post(
        "/api/segments/preview", json=group("and", [cond("total_spent", "between", 2000, value2=10000)]), headers=auth_headers
    )
    assert {m["name"] for m in resp.json()["members"]} == {"Bo Chen"}


def test_segment_members_transaction_count_greater_than(client, auth_headers):
    frequent = _create_customer(client, auth_headers, name="Ada Obi")
    rare = _create_customer(client, auth_headers, name="Bo Chen")
    for i in range(3):
        client.post(
            f"/api/customers/{frequent['id']}/transactions",
            json={"date": "2026-11-01", "item": "Item", "amount": 1000, "currency": "NGN"},
            headers=auth_headers,
        )
    client.post(
        f"/api/customers/{rare['id']}/transactions",
        json={"date": "2026-11-01", "item": "Item", "amount": 1000, "currency": "NGN"},
        headers=auth_headers,
    )

    resp = client.post(
        "/api/segments/preview", json=group("and", [cond("transaction_count", "greater_than", 1)]), headers=auth_headers
    )
    assert {m["name"] for m in resp.json()["members"]} == {"Ada Obi"}


def test_segment_members_last_purchase_within_days(client, auth_headers):
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

    resp = client.post(
        "/api/segments/preview", json=group("and", [cond("last_purchase_date", "within_last_days", 30)]), headers=auth_headers
    )
    assert {m["name"] for m in resp.json()["members"]} == {"Ada Obi"}


def test_segment_members_last_purchase_over_days_includes_never_purchased(client, auth_headers):
    never_bought = _create_customer(client, auth_headers, name="Ada Obi")
    recent_buyer = _create_customer(client, auth_headers, name="Bo Chen")
    client.post(
        f"/api/customers/{recent_buyer['id']}/transactions",
        json={"date": "2026-11-01", "item": "Rice", "amount": 1000, "currency": "NGN"},
        headers=auth_headers,
    )

    resp = client.post(
        "/api/segments/preview", json=group("and", [cond("last_purchase_date", "over_days_ago", 60)]), headers=auth_headers
    )
    members = resp.json()["members"]
    assert {m["name"] for m in members} == {"Ada Obi"}
    assert never_bought["id"] in [m["id"] for m in members]


def test_segment_members_has_unpaid_order(client, auth_headers):
    unpaid = _create_customer(client, auth_headers, name="Ada Obi")
    paid = _create_customer(client, auth_headers, name="Bo Chen")
    client.post(f"/api/customers/{unpaid['id']}/orders", json={"order_date": "2026-11-01", "items": [{"name": "Rice"}]}, headers=auth_headers)
    client.post(
        f"/api/customers/{paid['id']}/orders",
        json={"order_date": "2026-11-01", "items": [{"name": "Rice"}], "paid": True},
        headers=auth_headers,
    )

    resp = client.post("/api/segments/preview", json=group("and", [cond("has_unpaid_order", "equals", True)]), headers=auth_headers)
    assert {m["name"] for m in resp.json()["members"]} == {"Ada Obi"}


def test_segment_members_custom_field(client, auth_headers):
    _create_customer(client, auth_headers, name="Ada Obi", extra={"Car": "Camry"})
    _create_customer(client, auth_headers, name="Bo Chen", extra={"Car": "Civic"})

    resp = client.post("/api/segments/preview", json=group("and", [cond("extra.Car", "equals", "Camry")]), headers=auth_headers)
    assert {m["name"] for m in resp.json()["members"]} == {"Ada Obi"}


def test_segment_members_or_combinator(client, auth_headers):
    _create_customer(client, auth_headers, name="Ada Obi", status="lead")
    _create_customer(client, auth_headers, name="Bo Chen", status="inactive")
    _create_customer(client, auth_headers, name="Chi Eze", status="customer")

    resp = client.post(
        "/api/segments/preview",
        json=group("or", [cond("status", "equals", "lead"), cond("status", "equals", "inactive")]),
        headers=auth_headers,
    )
    assert {m["name"] for m in resp.json()["members"]} == {"Ada Obi", "Bo Chen"}


def test_segment_members_nor_combinator(client, auth_headers):
    _create_customer(client, auth_headers, name="Ada Obi", status="lead")
    _create_customer(client, auth_headers, name="Bo Chen", status="inactive")
    _create_customer(client, auth_headers, name="Chi Eze", status="customer")

    resp = client.post(
        "/api/segments/preview",
        json=group("nor", [cond("status", "equals", "lead"), cond("status", "equals", "inactive")]),
        headers=auth_headers,
    )
    assert {m["name"] for m in resp.json()["members"]} == {"Chi Eze"}


def test_segment_members_nested_group_combination(client, auth_headers):
    # (status = lead) OR (interests contains generator AND total_spent > 1000)
    lead_only = _create_customer(client, auth_headers, name="Ada Obi", status="lead")
    big_generator_buyer = _create_customer(client, auth_headers, name="Bo Chen", status="customer", interests="Generator")
    small_generator_buyer = _create_customer(client, auth_headers, name="Chi Eze", status="customer", interests="Generator")
    irrelevant = _create_customer(client, auth_headers, name="Dee Obi", status="customer", interests="Shoes")

    for cust, amount in [(big_generator_buyer, 5000), (small_generator_buyer, 100), (irrelevant, 5000)]:
        client.post(
            f"/api/customers/{cust['id']}/transactions",
            json={"date": "2026-11-01", "item": "Item", "amount": amount, "currency": "NGN"},
            headers=auth_headers,
        )

    query = group(
        "or",
        [
            cond("status", "equals", "lead"),
            group("and", [cond("interests", "contains", "generator"), cond("total_spent", "greater_than", 1000)]),
        ],
    )
    resp = client.post("/api/segments/preview", json=query, headers=auth_headers)
    assert {m["name"] for m in resp.json()["members"]} == {"Ada Obi", "Bo Chen"}


def test_empty_group_matches_everyone(client, auth_headers):
    _create_customer(client, auth_headers, name="Ada Obi")
    _create_customer(client, auth_headers, name="Bo Chen")

    resp = client.post("/api/segments/preview", json=group("and", []), headers=auth_headers)
    assert resp.json()["total"] == 2


def test_update_and_delete_segment(client, auth_headers):
    segment = client.post(
        "/api/segments", json={"name": "Leads", "filters": group("and", [cond("status", "equals", "lead")])}, headers=auth_headers
    ).json()
    updated = client.patch(f"/api/segments/{segment['id']}", json={"name": "Hot leads"}, headers=auth_headers).json()
    assert updated["name"] == "Hot leads"

    resp = client.delete(f"/api/segments/{segment['id']}", headers=auth_headers)
    assert resp.status_code == 204
    assert client.get("/api/segments", headers=auth_headers).json() == []
