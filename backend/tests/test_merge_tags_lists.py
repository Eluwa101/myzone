"""Covers the list blocks ({{#each ...}}) and filtered totals ({{count ...}},
{{sum ...}}, ...) - the merge tags that work on "some of this customer's
rows" rather than a single field."""
from datetime import date, timedelta


def _preview(client, auth_headers, customer_id, body_html):
    resp = client.post(
        "/api/messages/preview",
        json={"customer_id": customer_id, "subject": "x", "body_html": body_html},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    return resp.json()["body_html"]


def _days_ago(n: int) -> str:
    return (date.today() - timedelta(days=n)).isoformat()


def _customer_with_purchases(client, auth_headers):
    """Three transactions - two of them include a lighter."""
    customer = client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers).json()
    for days, items in (
        (100, [{"item": "Rice", "amount": 5000}]),
        (40, [{"item": "Gas Lighter", "qty": 2, "amount": 1000}, {"item": "Oil", "amount": 3000}]),
        (5, [{"item": "lighter", "amount": 600}]),
    ):
        resp = client.post(
            f"/api/customers/{customer['id']}/transactions",
            json={"date": _days_ago(days), "items": items, "currency": "NGN"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
    return customer


def test_each_lists_all_transactions_newest_first(client, auth_headers):
    customer = _customer_with_purchases(client, auth_headers)
    body = _preview(client, auth_headers, customer["id"], "{{#each transactions}}[{{number}}:{{date}}|{{items}}|{{currency}} {{amount}}]{{/each}}")
    assert body == (
        f"[1:{_days_ago(5)}|lighter|NGN 600.00]"
        f"[2:{_days_ago(40)}|Gas Lighter x2, Oil|NGN 4,000.00]"
        f"[3:{_days_ago(100)}|Rice|NGN 5,000.00]"
    )


def test_each_filters_to_transactions_containing_an_item(client, auth_headers):
    customer = _customer_with_purchases(client, auth_headers)
    body = _preview(client, auth_headers, customer["id"], '{{#each transactions where item contains "lighter"}}{{amount}};{{/each}}')
    assert body == "600.00;4,000.00;"


def test_each_sort_limit_and_multiple_conditions(client, auth_headers):
    customer = _customer_with_purchases(client, auth_headers)
    cid = customer["id"]
    assert _preview(client, auth_headers, cid, "{{#each transactions sort amount desc limit 2}}{{amount}};{{/each}}") == "5,000.00;4,000.00;"
    assert _preview(client, auth_headers, cid, "{{#each transactions sort date asc limit 1}}{{items}}{{/each}}") == "Rice"
    assert (
        _preview(client, auth_headers, cid, '{{#each transactions where item not contains "lighter" and amount >= 1000}}{{items}}{{/each}}')
        == "Rice"
    )
    assert _preview(client, auth_headers, cid, "{{#each transactions where date in last 30 days}}{{items}}{{/each}}") == "lighter"
    assert _preview(client, auth_headers, cid, f"{{{{#each transactions where date < {_days_ago(50)}}}}}{{{{items}}}}{{{{/each}}}}") == "Rice"


def test_each_over_line_items(client, auth_headers):
    customer = _customer_with_purchases(client, auth_headers)
    body = _preview(
        client, auth_headers, customer["id"], '{{#each transaction_items where item contains "lighter" sort date asc}}{{item}} x{{qty}} = {{amount}};{{/each}}'
    )
    assert body == "Gas Lighter x2 = 1,000.00;lighter x1 = 600.00;"


def test_each_else_branch_when_nothing_matches(client, auth_headers):
    customer = _customer_with_purchases(client, auth_headers)
    body = _preview(client, auth_headers, customer["id"], '{{#each transactions where item contains "bicycle"}}{{items}}{{else}}Nothing yet{{/each}}')
    assert body == "Nothing yet"
    assert _preview(client, auth_headers, customer["id"], '{{#each transactions where item contains "bicycle"}}{{items}}{{/each}}') == ""


def test_filtered_totals(client, auth_headers):
    customer = _customer_with_purchases(client, auth_headers)
    body = _preview(
        client,
        auth_headers,
        customer["id"],
        '{{count transactions where item contains "lighter"}} of {{count transactions}} / '
        '{{sum transaction_items.amount where item contains "lighter"}} / '
        '{{sum transaction_items.qty where item contains "lighter"}} / '
        "{{sum transactions.amount where date in last 60 days}} / {{max transactions.amount}} / {{min transactions.date}} / "
        "{{avg transactions.amount}}",
    )
    assert body == f"2 of 3 / 1,600.00 / 3 / 4,600.00 / 5,000.00 / {_days_ago(100)} / 3,200.00"


def test_totals_with_no_rows(client, auth_headers):
    customer = client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers).json()
    body = _preview(client, auth_headers, customer["id"], "{{count transactions}} / {{sum transactions.amount}} / {{max transactions.amount}}")
    assert body == "0 / 0.00 / —"


def test_each_over_orders(client, auth_headers):
    customer = client.post("/api/customers", json={"name": "Ada Obi"}, headers=auth_headers).json()
    for name, paid, delivered in (("Rice", False, False), ("Oil", True, True)):
        client.post(
            f"/api/customers/{customer['id']}/orders",
            json={"order_date": _days_ago(3), "items": [{"name": name}], "amount": 5000, "paid": paid, "delivered": delivered},
            headers=auth_headers,
        )
    cid = customer["id"]
    assert _preview(client, auth_headers, cid, "{{#each orders where delivered = no}}{{items}} paid:{{paid}}{{/each}}") == "Rice paid:No"
    assert _preview(client, auth_headers, cid, "{{#each orders where paid is true}}{{items}}{{/each}}") == "Oil"
    assert _preview(client, auth_headers, cid, "{{count order_items where delivered = yes}}") == "1"


def test_block_written_in_the_rich_text_editor(client, auth_headers):
    """Quill puts each line in its own <p>, HTML-encodes > and uses &nbsp;."""
    customer = _customer_with_purchases(client, auth_headers)
    body = _preview(
        client,
        auth_headers,
        customer["id"],
        "<p>Hi</p><p>{{#each transactions where amount &gt;=&nbsp;4000 sort amount asc}}</p><p><strong>{{items}}</strong></p><p>{{/each}}</p><p>Bye</p>",
    )
    assert body == "<p>Hi</p><p><strong>Gas Lighter x2, Oil</strong></p><p><strong>Rice</strong></p><p>Bye</p>"


def test_each_inside_html_table_and_outer_tags_still_resolve(client, auth_headers):
    customer = _customer_with_purchases(client, auth_headers)
    body = _preview(
        client,
        auth_headers,
        customer["id"],
        "<table>{{#each transactions limit 1}}<tr><td>{{customer.name}}</td><td>{{items}}</td></tr>{{/each}}</table>",
    )
    assert body == "<table><tr><td>Ada Obi</td><td>lighter</td></tr></table>"


def test_unparseable_blocks_are_left_visible(client, auth_headers):
    customer = _customer_with_purchases(client, auth_headers)
    for bad in (
        "{{#each invoices}}x{{/each}}",
        "{{#each transactions where colour = red}}x{{/each}}",
        "{{#each transactions where amount > lots}}x{{/each}}",
        "{{#each transactions limit many}}x{{/each}}",
        "{{sum transactions}}",
        "{{sum transactions.items}}",
        "{{count transactions where}}",
    ):
        assert _preview(client, auth_headers, customer["id"], bad) == bad


def test_values_are_html_escaped_in_the_body_but_not_the_subject(client, auth_headers):
    customer = client.post("/api/customers", json={"name": "Ada <b>Obi</b> & Co"}, headers=auth_headers).json()
    client.post(
        f"/api/customers/{customer['id']}/transactions",
        json={"date": _days_ago(1), "items": [{"item": "<script>x</script>", "amount": 10}], "currency": "NGN"},
        headers=auth_headers,
    )
    resp = client.post(
        "/api/messages/preview",
        json={
            "customer_id": customer["id"],
            "subject": "{{customer.name}}",
            "body_html": "<p>{{customer.name}}</p>{{#each transactions}}{{items}}{{/each}}",
        },
        headers=auth_headers,
    ).json()
    assert resp["subject"] == "Ada <b>Obi</b> & Co"
    assert resp["body_html"] == "<p>Ada &lt;b&gt;Obi&lt;/b&gt; &amp; Co</p>&lt;script&gt;x&lt;/script&gt;"


def test_list_snippets_appear_in_catalog_and_all_resolve(client, auth_headers):
    customer = _customer_with_purchases(client, auth_headers)
    tags = client.get("/api/messages/merge-tags", headers=auth_headers).json()
    snippets = [t for t in tags if t["category"] == "lists"]
    assert len(snippets) >= 10
    assert all(t["category_label"] == "Lists & totals" for t in snippets)
    for t in snippets:
        assert "{{" not in _preview(client, auth_headers, customer["id"], t["tag"]), t["key"]
