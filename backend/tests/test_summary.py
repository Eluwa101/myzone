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
