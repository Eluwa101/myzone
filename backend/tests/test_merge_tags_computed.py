"""Covers the arithmetic/date-computed merge tags specifically (stats.*,
system.*, and the computed customer/order/transaction fields) - all dates
are expressed relative to date.today() so these stay correct no matter
when the suite runs."""
from datetime import date, timedelta


def _preview(client, auth_headers, customer_id, body_html):
    resp = client.post(
        "/api/messages/preview",
        json={"customer_id": customer_id, "subject": "x", "body_html": body_html},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["body_html"]


def _create_customer(client, auth_headers, **extra):
    return client.post("/api/customers", json={"name": "Ada Obi", **extra}, headers=auth_headers).json()


def test_age_when_birthday_already_passed_this_year(client, auth_headers):
    today = date.today()
    birthday = date(today.year - 30, today.month, today.day) - timedelta(days=10)
    customer = _create_customer(client, auth_headers, birthday=birthday.isoformat())

    body = _preview(client, auth_headers, customer["id"], "Age {{customer.age}}")
    assert body == "Age 30"


def test_age_and_days_until_birthday_when_upcoming_this_year(client, auth_headers):
    today = date.today()
    shifted = today + timedelta(days=10)
    birth_year = today.year - 30
    birthday = date(birth_year, shifted.month, shifted.day)
    # expected age via the same month/day comparison the resolver uses -
    # if `shifted` crossed into January (today is in late December), the
    # "birthday already happened this year" case applies instead, same as
    # it would for the resolver
    expected_age = today.year - birth_year - (1 if (today.month, today.day) < (shifted.month, shifted.day) else 0)

    customer = _create_customer(client, auth_headers, birthday=birthday.isoformat())
    body = _preview(client, auth_headers, customer["id"], "Age {{customer.age}}, in {{customer.days_until_birthday}} days")
    assert f"Age {expected_age}," in body
    assert "in 10 days" in body


def test_age_and_birthday_missing_when_not_set(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    body = _preview(client, auth_headers, customer["id"], "{{customer.age}} / {{customer.days_until_birthday}}")
    assert body == "— / —"


def test_days_until_birthday_wraps_to_next_year(client, auth_headers):
    today = date.today()
    # a birthday that already happened this year (or is today) should
    # count down to NEXT year's occurrence, not show a negative/zero-ish
    # number from a date already in the past
    past_birthday = today - timedelta(days=5)
    customer = _create_customer(client, auth_headers, birthday=date(1990, past_birthday.month, past_birthday.day).isoformat())

    body = _preview(client, auth_headers, customer["id"], "{{customer.days_until_birthday}}")
    days = int(body)
    assert days >= 0
    assert days <= 366


def test_days_until_birthday_handles_feb_29(client, auth_headers):
    customer = _create_customer(client, auth_headers, birthday="2000-02-29")
    body = _preview(client, auth_headers, customer["id"], "{{customer.days_until_birthday}}")
    assert body.strip() != "—"
    assert 0 <= int(body) <= 366


def test_days_as_customer_is_zero_right_after_creation(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    body = _preview(client, auth_headers, customer["id"], "{{customer.days_as_customer}}")
    assert body == "0"


def test_stats_with_no_purchases(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    body = _preview(
        client,
        auth_headers,
        customer["id"],
        "{{stats.lifetime_spend}}|{{stats.transaction_count}}|{{stats.order_count}}|"
        "{{stats.average_transaction}}|{{stats.days_since_last_purchase}}|{{stats.first_purchase_date}}|"
        "{{stats.pending_order_count}}|{{stats.unpaid_order_total}}",
    )
    assert body == "0.00|0|0|—|—|—|0|0.00"


def test_stats_lifetime_spend_and_average(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    for amount in (5000, 15000):
        client.post(
            f"/api/customers/{customer['id']}/transactions",
            json={"date": "2026-01-01", "items": [{"item": "Rice", "amount": amount}], "currency": "NGN"},
            headers=auth_headers,
        )

    body = _preview(client, auth_headers, customer["id"], "{{stats.lifetime_spend}} / {{stats.transaction_count}} / {{stats.average_transaction}}")
    assert body == "20,000.00 / 2 / 10,000.00"


def test_stats_days_since_last_purchase_and_first_purchase_date(client, auth_headers):
    today = date.today()
    older = today - timedelta(days=20)
    newer = today - timedelta(days=3)
    customer = _create_customer(client, auth_headers)
    client.post(
        f"/api/customers/{customer['id']}/transactions",
        json={"date": older.isoformat(), "items": [{"item": "Rice", "amount": 1000}], "currency": "NGN"},
        headers=auth_headers,
    )
    client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": newer.isoformat(), "items": [{"name": "Generator"}]},
        headers=auth_headers,
    )

    body = _preview(client, auth_headers, customer["id"], "{{stats.days_since_last_purchase}} since / first was {{stats.first_purchase_date}}")
    assert body == f"3 since / first was {older.isoformat()}"


def test_stats_pending_and_unpaid_orders(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": "2026-01-01", "items": [{"name": "Rice"}], "amount": 5000, "paid": False, "delivered": False},
        headers=auth_headers,
    )
    client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": "2026-01-01", "items": [{"name": "Oil"}], "amount": 2000, "paid": True, "delivered": True},
        headers=auth_headers,
    )

    body = _preview(client, auth_headers, customer["id"], "{{stats.pending_order_count}} pending, {{stats.unpaid_order_total}} unpaid")
    assert body == "1 pending, 5,000.00 unpaid"


def test_latest_order_computed_dates(client, auth_headers):
    today = date.today()
    ordered = today - timedelta(days=4)
    due = today + timedelta(days=3)
    customer = _create_customer(client, auth_headers)
    client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": ordered.isoformat(), "delivery_date": due.isoformat(), "items": [{"name": "Generator"}]},
        headers=auth_headers,
    )

    body = _preview(
        client,
        auth_headers,
        customer["id"],
        "{{latest_order.days_since_ordered}} / {{latest_order.days_until_delivery}} / {{latest_order.overdue}}",
    )
    assert body == "4 / 3 / No"


def test_latest_order_overdue_when_delivery_date_passed_and_undelivered(client, auth_headers):
    today = date.today()
    overdue_date = today - timedelta(days=2)
    customer = _create_customer(client, auth_headers)
    client.post(
        f"/api/customers/{customer['id']}/orders",
        json={"order_date": (today - timedelta(days=10)).isoformat(), "delivery_date": overdue_date.isoformat(), "items": [{"name": "Generator"}], "delivered": False},
        headers=auth_headers,
    )

    body = _preview(client, auth_headers, customer["id"], "{{latest_order.overdue}}")
    assert body == "Yes"


def test_latest_transaction_days_since(client, auth_headers):
    today = date.today()
    tx_date = today - timedelta(days=7)
    customer = _create_customer(client, auth_headers)
    client.post(
        f"/api/customers/{customer['id']}/transactions",
        json={"date": tx_date.isoformat(), "items": [{"item": "Rice", "amount": 1000}], "currency": "NGN"},
        headers=auth_headers,
    )

    body = _preview(client, auth_headers, customer["id"], "{{latest_transaction.days_since}}")
    assert body == "7"


def test_system_tags(client, auth_headers):
    customer = _create_customer(client, auth_headers)
    today = date.today()
    body = _preview(client, auth_headers, customer["id"], "{{system.today}} / {{system.year}}")
    assert body == f"{today.isoformat()} / {today.year}"


def test_computed_merge_tags_appear_in_catalog(client, auth_headers):
    tags = client.get("/api/messages/merge-tags", headers=auth_headers).json()
    tag_strings = {t["tag"] for t in tags}
    assert "{{stats.lifetime_spend}}" in tag_strings
    assert "{{customer.days_until_birthday}}" in tag_strings
    assert "{{latest_order.days_until_delivery}}" in tag_strings
    assert "{{system.today}}" in tag_strings
