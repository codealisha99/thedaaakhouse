"""JD submission + storage tests (authenticated)."""


def test_create_and_get_job(client, auth_headers):
    payload = {
        "title": "AI Engineer",
        "company_name": "Acme",
        "location": "Remote",
        "raw_text": "We need RAG, vector databases, and FastAPI experience.",
    }
    r = client.post("/api/jobs", json=payload, headers=auth_headers)
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]

    r2 = client.get(f"/api/jobs/{job_id}", headers=auth_headers)
    assert r2.status_code == 200
    assert r2.json()["title"] == "AI Engineer"
    assert r2.json()["status"] == "created"


def test_empty_jd_rejected(client, auth_headers):
    r = client.post("/api/jobs", json={"title": "X", "raw_text": "   "}, headers=auth_headers)
    assert r.status_code == 400


def test_future_workflows_not_ready_but_visible(client, auth_headers):
    payload = {"title": "AI Engineer", "raw_text": "Build LLM apps with RAG."}
    job_id = client.post("/api/jobs", json=payload, headers=auth_headers).json()["id"]
    for op in ["analyze", "match", "tailor-resume", "company-research", "interview-prep", "project-recommendations"]:
        r = client.post(f"/api/jobs/{job_id}/{op}", headers=auth_headers)
        assert r.status_code == 501, op
