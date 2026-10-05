"""Application tracker CRUD + persistence tests."""


def test_create_lists_persists(client, auth_headers, sample_jd):
    r = client.post(
        "/api/applications",
        json={"company": "Acme", "role": "AI Engineer", "status": "saved", "raw_jd": sample_jd},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    app_id = r.json()["id"]
    assert r.json()["jd_analysis"] is not None  # auto-analyzed on create
    assert "rag" in (r.json()["jd_analysis"] or {}).get("skills", [])

    # persists across requests (new session each request in tests)
    assert client.get(f"/api/applications/{app_id}", headers=auth_headers).status_code == 200
    rows = client.get("/api/applications", headers=auth_headers).json()
    assert len(rows) == 1 and rows[0]["company"] == "Acme"


def test_status_flow_and_history(client, auth_headers):
    app_id = client.post(
        "/api/applications", json={"company": "Acme", "role": "Eng"}, headers=auth_headers
    ).json()["id"]
    r = client.patch(f"/api/applications/{app_id}", json={"status": "applied"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "applied"
    hist = r.json()["status_history"]
    assert hist[-1] == {"from": "saved", "to": "applied", "at": hist[-1]["at"]}

    r = client.patch(f"/api/applications/{app_id}", json={"status": "bogus"}, headers=auth_headers)
    assert r.status_code == 400


def test_search_filter_sort_and_delete(client, auth_headers):
    for company, status in [("Acme", "saved"), ("Beta", "applied"), ("Acme Labs", "interview")]:
        client.post(
            "/api/applications",
            json={"company": company, "role": "Eng", "status": status},
            headers=auth_headers,
        )
    assert len(client.get("/api/applications?search=acme", headers=auth_headers).json()) == 2
    assert len(client.get("/api/applications?status=applied", headers=auth_headers).json()) == 1

    app_id = client.get("/api/applications", headers=auth_headers).json()[0]["id"]
    assert client.delete(f"/api/applications/{app_id}", headers=auth_headers).status_code == 204
    assert len(client.get("/api/applications", headers=auth_headers).json()) == 2


def test_pagination_envelope_and_legacy_shape(client, auth_headers):
    for i in range(5):
        client.post(
            "/api/applications",
            json={"company": f"C{i}", "role": "Eng"},
            headers=auth_headers,
        )
    legacy = client.get("/api/applications", headers=auth_headers).json()
    assert isinstance(legacy, list) and len(legacy) == 5  # default shape unchanged

    p1 = client.get("/api/applications?page=1&page_size=2", headers=auth_headers).json()
    assert p1["total"] == 5 and p1["page"] == 1 and len(p1["items"]) == 2
    p3 = client.get("/api/applications?page=3&page_size=2", headers=auth_headers).json()
    assert len(p3["items"]) == 1
    assert client.get("/api/applications?page=1&page_size=101", headers=auth_headers).status_code == 422
