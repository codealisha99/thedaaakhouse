"""Step 05: evidence extraction, persistence, and confirm/reject API."""

from app.db import models

RESUME = """Sam Lee
sam@example.com 555-0199
github.com/samlee

EXPERIENCE
Senior Backend Engineer, Beta Corp, 2020-2025
- Built RAG pipelines with Python and FastAPI serving 10k users
- Shipped Docker images to Kubernetes clusters

PROJECTS
Retrieval demo
- Built vector search with pgvector and OpenAI embeddings

EDUCATION
BS Computer Science, 2016-2020

SKILLS
Python, FastAPI, Docker, Kubernetes, SQL

CERTIFICATIONS
AWS Certified Developer
"""


def _upload(client, auth_headers, text=RESUME):
    r = client.post("/api/resumes",
                    files={"file": ("r.txt", text.encode(), "text/plain")},
                    headers=auth_headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_evidence_rows_persisted(client, auth_headers, db_session=None):
    rid = _upload(client, auth_headers)
    import sqlite3
    # the app's db engine is behind dependency overrides; query via API + facts
    r = client.get(f"/api/resumes/{rid}/evidence", headers=auth_headers)
    assert r.status_code == 200, r.text
    items = r.json()
    kinds = {i["kind"] for i in items}
    assert {"contact", "skill", "experience", "achievement"} <= kinds
    assert items[0]["ev_ref"] == "ev1" and items[0]["source_text"]
    demonstrated = {i["label"].casefold() for i in items
                    if i["kind"] == "skill" and i["assert_type"] == "demonstrated"}
    claimed = {i["label"].casefold() for i in items
               if i["kind"] == "skill" and i["assert_type"] == "claimed"}
    assert "kubernetes" in demonstrated      # found inside a bullet
    assert "sql" in claimed and "sql" not in demonstrated  # skills list only


def test_evidence_confirm_reject_and_scoping(client, auth_headers):
    rid = _upload(client, auth_headers)
    items = client.get(f"/api/resumes/{rid}/evidence", headers=auth_headers).json()
    tgt = next(i for i in items if i["kind"] == "skill" and i["label"] == "SQL")
    r2 = client.patch(f"/api/resumes/{rid}/evidence/{tgt['id']}",
                      json={"status": "rejected"}, headers=auth_headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["status"] == "rejected"
    assert r2.json()["confirmed_at"] is not None

    r3 = client.post("/api/auth/register",
                     json={"username": "otherone", "password": "password123"})
    other = {"Authorization": f"Bearer {r3.json()['access_token']}"}
    assert client.get(f"/api/resumes/{rid}/evidence", headers=other).status_code == 404
    assert client.patch(f"/api/resumes/{rid}/evidence/{tgt['id']}",
                        json={"status": "confirmed"}, headers=other).status_code == 404


def test_evidence_status_validation(client, auth_headers):
    rid = _upload(client, auth_headers)
    ev = client.get(f"/api/resumes/{rid}/evidence", headers=auth_headers).json()[0]
    r = client.patch(f"/api/resumes/{rid}/evidence/{ev['id']}",
                     json={"status": "maybe"}, headers=auth_headers)
    assert r.status_code == 400
