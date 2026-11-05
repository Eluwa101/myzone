def test_summary_aggregates_match_seeded_data(client, auth_headers):
    ada = client.post(
        "/api/customers",
        json={"name": "Ada Obi", "interests": "Generator"},
        headers=auth_headers,
    ).json()
    bo = client.post(
        "/api/customers",
        json={"name": "Bo Chen"},
        params={"force": True},
        headers=auth_headers,
    ).json()

    client.post(
        f"/api/customers/{ada['id']}/transactions",
        json={"date": "2026-11-01", "item": "Rice", "qty": 2, "amount": 15000, "currency": "NGN"},
        headers=auth_headers,
    )
    client.post(
        f"/api/customers/{bo['id']}/transactions",
        json={"date": "2026-11-02", "item": "Oil", "qty": 1, "amount": 50, "currency": "USD"},
        headers=auth_headers,
    )

    summary = client.get("/api/summary", headers=auth_headers).json()
    assert summary["total_customers"] == 2
    assert summary["all_time_by_currency"]["NGN"] == 30000
    assert summary["all_time_by_currency"]["USD"] == 50
    assert summary["this_month_by_currency"]["NGN"] == 30000
    top_names = {c["name"] for c in summary["top_customers"]}
    assert top_names == {"Ada Obi", "Bo Chen"}


def test_ranged_summary_scopes_transactions_by_date_and_drops_this_month(client, auth_headers):
    ada = client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers).json()
    client.post(
        f"/api/customers/{ada['id']}/transactions",
        json={"date": "2026-01-15", "item": "Rice", "qty": 1, "amount": 5000, "currency": "NGN"},
        headers=auth_headers,
    )
    client.post(
        f"/api/customers/{ada['id']}/transactions",
        json={"date": "2026-11-01", "item": "Oil", "qty": 1, "amount": 2000, "currency": "NGN"},
        headers=auth_headers,
    )

    ranged = client.get("/api/summary", params={"start_date": "2026-01-01", "end_date": "2026-01-31"}, headers=auth_headers).json()
    assert ranged["all_time_by_currency"]["NGN"] == 5000
    assert ranged["this_month_by_currency"] == {}
    assert ranged["range_start"] == "2026-01-01"
    assert ranged["range_end"] == "2026-01-31"
    assert [m["month"] for m in ranged["last_6_months"]] == ["2026-01"]


def test_ranged_summary_scopes_customer_count_by_created_at(client, auth_headers):
    client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers)

    far_future = client.get(
        "/api/summary", params={"start_date": "2099-01-01", "end_date": "2099-12-31"}, headers=auth_headers
    ).json()
    assert far_future["total_customers"] == 0

    all_time = client.get("/api/summary", headers=auth_headers).json()
    assert all_time["total_customers"] == 1


def test_top_customers_and_monthly_drilldown_endpoints(client, auth_headers):
    ada = client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers).json()
    client.post(
        f"/api/customers/{ada['id']}/transactions",
        json={"date": "2026-11-01", "item": "Rice", "qty": 1, "amount": 1000, "currency": "NGN"},
        headers=auth_headers,
    )

    top = client.get("/api/summary/top-customers", headers=auth_headers).json()
    assert {t["name"] for t in top} == {"Ada Obi"}

    months = client.get("/api/summary/monthly", headers=auth_headers).json()
    assert any(m["month"] == "2026-11" for m in months)
