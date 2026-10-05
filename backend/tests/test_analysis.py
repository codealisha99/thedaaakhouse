"""End-to-end connected flow: tailor → attach → ATS → interview prep.

Uses real analyzers on real text. Asserts computed values, not placeholders.
"""


def _upload_resume(client, auth_headers, text):
    r = client.post(
        "/api/resumes",
        files={"file": ("resume.txt", text.encode(), "text/plain")},
        headers=auth_headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_full_connected_flow(client, auth_headers, sample_jd, sample_resume):
    resume_id = _upload_resume(client, auth_headers, sample_resume)
    app_id = client.post(
        "/api/applications",
        json={"company": "Acme", "role": "Senior AI Engineer", "status": "applied", "raw_jd": sample_jd},
        headers=auth_headers,
    ).json()["id"]

    # 1. Tailor → new version, auto-attached
    t = client.post(f"/api/applications/{app_id}/tailor", json={"resume_id": resume_id}, headers=auth_headers)
    assert t.status_code == 201, t.text
    version_id = t.json()["id"]
    detail = client.get(f"/api/applications/{app_id}", headers=auth_headers).json()
    assert detail["application"]["resume_version_id"] == version_id
    assert any(v["id"] == version_id for v in detail["versions"])

    # version content preserves every original line (extractive guarantee)
    v = client.get(f"/api/applications/versions/{version_id}", headers=auth_headers).json()
    assert sorted(v["content"].splitlines()) == sorted(sample_resume.splitlines())
    assert "kubernetes" in v["missing_keywords"]  # honestly reported, not filled

    # 2. ATS on the tailored version → real computed score
    a = client.post(f"/api/applications/{app_id}/ats", json={"resume_version_id": version_id}, headers=auth_headers)
    assert a.status_code == 201, a.text
    body = a.json()
    assert 0 < body["score"] < 100
    assert "kubernetes" in body["breakdown"]["skills_missing"]
    assert body["breakdown"]["methodology"].startswith("0.50")
    assert client.get(f"/api/applications/{app_id}", headers=auth_headers).json()["application"]["ats_score"] == body["score"]

    # 3. Interview prep derived from the actual JD
    p = client.post(
        f"/api/applications/{app_id}/interview-prep", json={"resume_id": resume_id}, headers=auth_headers
    )
    assert p.status_code == 201, p.text
    plan = p.json()["plan"]
    assert any("rag" in q["question"].lower() for q in plan["questions"])
    assert all({"category", "reason", "source"} <= set(q) for q in plan["questions"])

    # 4. ATS without any JD fails honestly (no fabrication path)
    bare_id = client.post(
        "/api/applications", json={"company": "NoJD", "role": "Eng"}, headers=auth_headers
    ).json()["id"]
    bad = client.post(f"/api/applications/{bare_id}/ats", json={"resume_id": resume_id}, headers=auth_headers)
    assert bad.status_code == 400
