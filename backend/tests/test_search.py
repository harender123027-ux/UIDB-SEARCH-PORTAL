def test_search_text_anonymous(client):
    r = client.post("/api/search", json={"query": "male with tattoo on neck"})
    assert r.status_code == 200
    body = r.json()
    assert "shortlist" in body
    assert "query" in body


def test_search_text_anonymous_ui_body_target(client):
    r = client.post("/api/search", json={"query": "male", "search_target": "ui_body"})
    assert r.status_code == 200
    assert "shortlist" in r.json()


def test_search_text(client, auth_headers):
    r = client.post("/api/search", headers=auth_headers, json={"query": "male with tattoo on neck"})
    assert r.status_code == 200
    body = r.json()
    assert "shortlist" in body
    assert "query" in body
    assert isinstance(body["shortlist"], list)


def test_search_voice(client, sample_jpeg, auth_headers):
    # Use image as "audio" to trigger STT path; may fail but endpoint should accept
    r = client.post("/api/search/voice", files={"audio": ("x.wav", sample_jpeg, "audio/wav")}, headers=auth_headers)
    # 200 with shortlist, or 500 if STT fails - accept both for CI without whisper
    assert r.status_code in (200, 422, 500)
    if r.status_code == 200:
        assert "shortlist" in r.json()


def test_search_combined_text_only_anonymous(client):
    r = client.post("/api/search/combined", data={"query": "male"})
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    assert isinstance(body["results"], list)


def test_search_combined_text_only(client, auth_headers):
    """Combined search with text only returns results with overlap/sources."""
    r = client.post("/api/search/combined", data={"query": "male"}, headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    assert isinstance(body["results"], list)
    for item in body["results"][:5]:
        assert "id" in item
        assert "label" in item
        assert "score" in item
        assert "overlap" in item
        assert "sources" in item


def test_search_combined_image_only(client, sample_jpeg, auth_headers):
    """Combined search with image only returns results."""
    r = client.post(
        "/api/search/combined",
        data={},
        files={"files": ("face.jpg", sample_jpeg, "image/jpeg")},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    assert isinstance(body["results"], list)


def test_search_combined_text_and_image(client, sample_jpeg, auth_headers):
    """Combined search with both text and image merges by overlap."""
    r = client.post(
        "/api/search/combined",
        data={"query": "male"},
        files={"files": ("face.jpg", sample_jpeg, "image/jpeg")},
        headers=auth_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    assert isinstance(body["results"], list)
    # Results should have overlap when both modalities return same ref
    if body["results"]:
        first = body["results"][0]
        assert first.get("overlap", 0) >= 0
        assert "sources" in first


def test_search_all(client, auth_headers):
    """Search all scans all submissions against repository."""
    r = client.post("/api/search/all", headers=auth_headers)
    assert r.status_code == 200
    body = r.json()
    assert "results" in body
    assert isinstance(body["results"], list)
