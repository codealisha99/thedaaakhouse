"""Nexora end-to-end workflow tests: fixture, trace, errors, permissions."""

import io

from app.fixtures import nexora


def _user(client, name):
    r = client.post("/api/auth/register", json={"username": name, "password": "password123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _pdf_bytes(lines):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    for line in lines:
        pdf.cell(0, 7, line, new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


def test_fixture_labels_fictional():
    assert "fictional" in nexora.COMPANY.lower()
    assert "fictional" in nexora.JD_TEXT.lower()
    assert "FICTIONAL" in nexora.MARKER


def test_seed_idempotent_and_user_scoped(client):
    h1 = _user(client, "seed_a")
    r1 = client.post("/api/dev/seed-nexora", headers=h1)
    assert r1.status_code == 201 and r1.json()["seeded"] is True
    r2 = client.post("/api/dev/seed-nexora", headers=h1)
    assert r2.json()["seeded"] is False
    assert r2.json()["application_id"] == r1.json()["application_id"]
    h2 = _user(client, "seed_b")
    r3 = client.post("/api/dev/seed-nexora", headers=h2)
    assert r3.json()["seeded"] is True
    assert r3.json()["application_id"] != r1.json()["application_id"]
    app = client.get(f"/api/applications/{r1.json()['application_id']}", headers=h1).json()
    assert "fictional" in app["application"]["company"].lower()
    assert nexora.MARKER in (app["application"]["notes"] or "")


def test_seed_blocked_in_production(client, monkeypatch):
    import app.api.routes.dev as devmod
    from app.core.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        h = _user(client, "seed_prod")
        assert client.post("/api/dev/seed-nexora", headers=h).status_code == 404
    finally:
        monkeypatch.delenv("ENVIRONMENT", raising=False)
        get_settings.cache_clear()


def test_optimize_missing_resume_404(client):
    h = _user(client, "noroom")
    aid = client.post("/api/applications", json={"company": "C", "role": "R", "raw_jd": "Need Python."},
                      headers=h).json()["id"]
    r = client.post(f"/api/applications/{aid}/optimize", json={"resume_id": "nope"}, headers=h)
    assert r.status_code == 404


def test_real_pdf_extraction_sections():
    pdf = _pdf_bytes(["Jane Doe", "jane@example.com", "EXPERIENCE", "Built Python APIs", "SKILLS", "Python"])
    from app.ingestion.docparse import parse_upload

    out = parse_upload("cv.pdf", "application/pdf", pdf)
    assert out["parse_status"] == "parsed" or "experience" in out["sections"]
    assert "Python" in out["text"]


def test_garbage_pdf_fails_with_reason():
    from app.ingestion.docparse import parse_upload

    out = parse_upload("bad.pdf", "application/pdf", b"not a pdf at all")
    assert out["parse_status"] in ("empty", "failed")
    assert out["warnings"]


def test_ats_score_scale_and_determinism(client):
    h = _user(client, "scale")
    rid = client.post("/api/resumes",
                      files={"file": ("r.txt", b"Sam\n- Built Python APIs\nSKILLS\nPython", "text/plain")},
                      headers=h).json()["id"]
    aid = client.post("/api/applications", json={"company": "C", "role": "R", "raw_jd": "Need Python, Docker."},
                      headers=h).json()["id"]
    s1 = client.post(f"/api/applications/{aid}/ats-v2", json={"resume_id": rid}, headers=h).json()["score"]
    s2 = client.post(f"/api/applications/{aid}/ats-v2", json={"resume_id": rid}, headers=h).json()["score"]
    assert 0 <= s1 <= 100 and s1 == s2


def test_fit_skipped_without_profile_records_stage(client):
    h = _user(client, "noprof")
    rid = client.post("/api/resumes",
                      files={"file": ("r.txt", b"Sam\nSKILLS\nPython", "text/plain")},
                      headers=h).json()["id"]
    aid = client.post("/api/applications", json={"company": "C", "role": "R", "raw_jd": "Need Cobol."},
                      headers=h).json()["id"]
    run = client.post(f"/api/applications/{aid}/optimize", json={"resume_id": rid}, headers=h).json()
    stages = {s["stage"]: s for s in run.get("stage_trace", [])}
    assert stages["career_fit"]["status"] == "skipped"


def test_failed_run_persists_failed_trace(client, monkeypatch):
    h = _user(client, "failrun")
    rid = client.post("/api/resumes",
                      files={"file": ("r.txt", b"Sam\nSKILLS\nPython", "text/plain")},
                      headers=h).json()["id"]
    aid = client.post("/api/applications",
                      json={"company": "C", "role": "R",
                            "raw_jd": "Need Kubernetes, Terraform, Go, Rust, Postgres, Kafka."},
                      headers=h).json()["id"]
    from app import services as svcmod

    def boom(self, obj, resume, label=None, **kw):
        raise RuntimeError("simulated tailor outage")

    monkeypatch.setattr(svcmod.ApplicationService, "tailor", boom)
    import pytest

    with pytest.raises(RuntimeError, match="simulated tailor outage"):
        client.post(f"/api/applications/{aid}/optimize", json={"resume_id": rid}, headers=h)
    runs = client.get("/api/optimize/runs", headers=h).json()
    failed = [x for x in runs if x["status"] == "failed"]
    assert failed, runs
    assert any(s["status"] == "failed" for s in failed[0].get("stage_trace", []))
    monkeypatch.undo()
    # service recovers; a retry runs cleanly and does not corrupt data
    r2 = client.post(f"/api/applications/{aid}/optimize", json={"resume_id": rid}, headers=h)
    assert r2.status_code == 201


def test_download_permissions_isolated(client):
    h1 = _user(client, "owner1")
    rid = client.post("/api/resumes",
                      files={"file": ("r.txt", b"Sam\nSKILLS\nPython", "text/plain")},
                      headers=h1).json()["id"]
    aid = client.post("/api/applications", json={"company": "C", "role": "R", "raw_jd": "Need Python."},
                      headers=h1).json()["id"]
    run_id = client.post(f"/api/applications/{aid}/optimize", json={"resume_id": rid}, headers=h1).json()["id"]
    h2 = _user(client, "stranger")
    assert client.get(f"/api/optimize/runs/{run_id}", headers=h2).status_code == 404
    assert client.get(f"/api/optimize/runs/{run_id}/latex", headers=h2).status_code == 404
    assert client.get(f"/api/optimize/runs/{run_id}/latex").status_code in (401, 403)


def test_latex_invalid_detected():
    from app.resume.latex.template import validate_latex

    assert validate_latex("plain text, no structure")["valid"] is False
    good = "\\documentclass{article}\n\\begin{document}\n\\section*{Skills}\nPython\n\\end{document}\n"
    assert validate_latex(good)["valid"] is True
