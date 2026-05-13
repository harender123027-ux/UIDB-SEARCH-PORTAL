def test_audit_list(client, auth_headers):
    r = client.get("/api/audit", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_audit_pagination(client, auth_headers):
    r = client.get("/api/audit?limit=5&offset=0", headers=auth_headers)
    assert r.status_code == 200
    assert isinstance(r.json(), list)
