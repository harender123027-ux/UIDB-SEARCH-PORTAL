def test_dashboard(client, auth_headers):
    r = client.get("/api/dashboard", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "total_submissions" in body
    assert "pending_review" in body
    assert "matched" in body
    assert "recent" in body
    assert isinstance(body["recent"], list)
