def test_create_widget_defaults_title_to_truncated_question(client, auth_headers):
    long_question = "Who are my top ten customers by total spend across all currencies this year and last year combined?"
    resp = client.post("/api/dashboard/widgets", json={"question": long_question}, headers=auth_headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == long_question[:60].rstrip() + "…"
    assert body["question"] == long_question


def test_create_widget_with_explicit_title(client, auth_headers):
    resp = client.post("/api/dashboard/widgets", json={"question": "Who spent the most?", "title": "Top spender"}, headers=auth_headers)
    assert resp.json()["title"] == "Top spender"


def test_list_and_delete_widget(client, auth_headers):
    created = client.post("/api/dashboard/widgets", json={"question": "Any churn risks?"}, headers=auth_headers).json()
    listing = client.get("/api/dashboard/widgets", headers=auth_headers).json()
    assert len(listing) == 1
    assert listing[0]["id"] == created["id"]

    resp = client.delete(f"/api/dashboard/widgets/{created['id']}", headers=auth_headers)
    assert resp.status_code == 204
    assert client.get("/api/dashboard/widgets", headers=auth_headers).json() == []


def test_widgets_require_auth(client):
    resp = client.get("/api/dashboard/widgets")
    assert resp.status_code == 401
