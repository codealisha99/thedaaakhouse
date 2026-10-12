"""Resume Studio tests: edit, compare, match report, PDF export."""

RESUME = ("Sam Lee\nsam@example.com\n\nEXPERIENCE\nDev, Z, 2020-2025\n"
          "- Built Python APIs with FastAPI\n- Shipped Docker images\n\nSKILLS\nPython, FastAPI")
JD = "Backend role. Requirements: Python, FastAPI, Docker, Kubernetes."


def _setup(client, auth_headers):
    r = client.post("/api/resumes",
                    files={"file": ("r.txt", RESUME.encode(), "text/plain")},
                    headers=auth_headers)
    assert r.status_code == 201, r.text
    rid = r.json()["id"]
    a = client.post("/api/applications",
                    json={"company": "S", "role": "R", "raw_jd": JD},
                    headers=auth_headers).json()
    v = client.post(f"/api/applications/{a['id']}/tailor", json={"resume_id": rid},
                    headers=auth_headers).json()
    return a["id"], rid, v["id"]


def test_patch_version_label_only(client, auth_headers):
    _, _, vid = _setup(client, auth_headers)
    r = client.patch(f"/api/applications/versions/{vid}", json={"label": "My label"},
                     headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["label"] == "My label"
    assert r.json()["edited_manually"] is False


def test_patch_version_content_flags_edit(client, auth_headers):
    _, _, vid = _setup(client, auth_headers)
    before = client.get(f"/api/applications/versions/{vid}", headers=auth_headers).json()
    r = client.patch(f"/api/applications/versions/{vid}",
                     json={"content": before["content"] + "\nExtra line I wrote myself."},
                     headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["edited_manually"] is True


def test_patch_version_rejects_empty_and_missing(client, auth_headers):
    _, _, vid = _setup(client, auth_headers)
    assert client.patch(f"/api/applications/versions/{vid}", json={"content": "  "},
                        headers=auth_headers).status_code == 400
    assert client.patch("/api/applications/versions/nope", json={"label": "x"},
                        headers=auth_headers).status_code == 404


def test_compare_proves_extractive(client, auth_headers):
    _, _, vid = _setup(client, auth_headers)
    r = client.get(f"/api/applications/versions/{vid}/compare", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["same_line_set"] is True
    assert body["added"] == [] and body["removed"] == []


def test_compare_after_manual_edit_shows_added(client, auth_headers):
    _, _, vid = _setup(client, auth_headers)
    client.patch(f"/api/applications/versions/{vid}", json={"content": "x\nInvented line."},
                 headers=auth_headers)
    body = client.get(f"/api/applications/versions/{vid}/compare", headers=auth_headers).json()
    assert body["same_line_set"] is False
    assert any("Invented" in l for l in body["added"])


def test_match_report_rows_and_coverage(client, auth_headers):
    aid, _, _ = _setup(client, auth_headers)
    r = client.get(f"/api/applications/{aid}/match-report", headers=auth_headers)
    assert r.status_code == 200, r.text
    body = r.json()
    by_req = {row["requirement"]: row for row in body["rows"]}
    assert by_req["python"]["status"] == "matched"
    assert by_req["python"]["evidence"]
    assert by_req["kubernetes"]["status"] == "missing"
    assert 0.0 < body["coverage"] < 1.0


def test_match_report_no_jd_400(client, auth_headers):
    aid = client.post("/api/applications", json={"company": "N", "role": "R"},
                      headers=auth_headers).json()["id"]
    assert client.get(f"/api/applications/{aid}/match-report", headers=auth_headers).status_code == 400


def test_pdf_export(client, auth_headers):
    _, _, vid = _setup(client, auth_headers)
    r = client.get(f"/api/applications/versions/{vid}/pdf", headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"] == "application/pdf"
    assert r.content.startswith(b"%PDF")
    assert ".pdf" in r.headers["content-disposition"]


def test_pdf_missing_404(client, auth_headers):
    assert client.get("/api/applications/versions/nope/pdf", headers=auth_headers).status_code == 404
