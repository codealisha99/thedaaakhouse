"""ATS v2 tests: stages, weights, unknowns, blockers, determinism."""

from app.analysis.ats_v2 import analyze_ats_v2, split_requirements

RESUME = """Sam Lee
sam@example.com 555-0199

EXPERIENCE
Backend Engineer, Z 2020-2025
- Built Python APIs with FastAPI serving 10k users
- Shipped Docker images to Kubernetes clusters

EDUCATION
BS Computer Science, 2016-2020

SKILLS
Python, FastAPI, Docker, SQL, sklearn
"""

ENG_JD = """Senior Backend Engineer. Requirements: 4+ years Python, FastAPI, Docker, Kubernetes.
Preferred: Terraform, Go. Education: BS in Computer Science."""

SALES_JD = """Sales Engineer. Demo our Python platform, travel to clients.
Requirements: presentations, travel, Python. Preferred: charisma."""


def test_alias_matching():
    out = analyze_ats_v2("Data scientist. Uses scikit learn daily for models.", "Need scikit-learn.")
    kinds = {e["requirement"]: e["kind"] for e in out["matched"]}
    assert kinds.get("scikit-learn") == "alias"


def test_required_vs_preferred_weighting():
    req_only = analyze_ats_v2(RESUME, "Requirements:\nPython.")
    assert req_only["categories"]["skills"]["score"] == 100.0
    with_pref = analyze_ats_v2(RESUME, "Requirements:\nPython.\nPreferred:\nTerraform, Go, Rust.")
    # missing preferred dents but does not tank like a required miss
    assert 50.0 < with_pref["categories"]["skills"]["score"] < 100.0


def test_partial_and_semantic_stages():
    out = analyze_ats_v2("I do machine learning models.", "Need machine learning.")
    assert any(e["kind"] in ("partial", "semantic", "exact") for e in out["matched"] + out["missing"])
    out2 = analyze_ats_v2("I build retrieval over vector stores at scale.",
                          "Need vector databases for retrieval. Our vector databases serve 1M queries.")
    assert any(e["kind"] == "semantic" for e in out2["matched"]), out2["matched"]


def test_evidence_strength_sections():
    doc = {"sections": {"experience": "Built Python APIs with FastAPI",
                        "skills": "Python, FastAPI, Docker, SQL"}, "warnings": []}
    out = analyze_ats_v2(RESUME, "Need Python, SQL.", parsed_doc=doc)
    by_req = {e["requirement"]: e for e in out["matched"]}
    assert by_req["python"]["strength"] == "strong"  # in EXPERIENCE section
    assert by_req["sql"]["strength"] == "documented"  # skills list only


def test_unknown_categories_excluded_not_zeroed():
    out = analyze_ats_v2(RESUME, "Need Python. No degree mentioned, no years mentioned.")
    assert out["categories"]["education"]["score"] is None
    # neither side states years AND the resume's date ranges (2020-2025,
    # 2016-2020) are countable — experience of 9y is evidence-derived, not guessed
    assert out["categories"]["experience"]["score"] == 100.0
    assert "from date ranges" in out["categories"]["experience"]["detail"]
    total_w = sum(c["weight"] for c in out["categories"].values() if c["score"] is not None)
    assert abs(total_w - 1.0) < 0.01


def test_experience_unknown_when_no_years_and_no_dates():
    out = analyze_ats_v2("Built APIs in Python. Used Docker.",
                         "Principal role, requires 10+ years Python.")
    assert out["categories"]["experience"]["score"] is None
    assert not any("Experience blocker" in b for b in out["blockers"])  # never fabricated
    assert any("make tenures explicit" in r.lower() or "explicit" in r.lower()
               for r in out["recommendations"])


def test_blockers_reported_separately():
    jd = "Principal role.\nRequirements:\n15+ years Python.\nEducation: PhD required."
    out = analyze_ats_v2(RESUME, jd)
    # resume date ranges support 10y vs 15 required — a real, countable gap
    assert any("Experience blocker" in b for b in out["blockers"])
    assert any("Education blocker" in b for b in out["blockers"])


def test_deterministic_and_full_breakdown():
    a = analyze_ats_v2(RESUME, ENG_JD)
    b = analyze_ats_v2(RESUME, ENG_JD)
    assert a["score"] == b["score"] and a == b
    assert 0 <= a["score"] <= 100
    assert set(a["categories"]) == {"skills", "experience", "projects", "education", "semantic", "parse"}
    assert a["methodology"] and a["weights"] and a["provenance"]["jd_sha256"]
    assert a["recommendations"]


def test_unrelated_high_overlap_scores_lower():
    eng = analyze_ats_v2(RESUME, ENG_JD)["score"]
    # A JD with no technical requirements at all: nothing substantive to match.
    empty = analyze_ats_v2(RESUME, "Sales Manager.\nRequirements:\nleadership, targets, travel.")["score"]
    assert empty < eng, (empty, eng)
    # And when overlap exists, the fit engine (not ATS) is what rejects the role:
    from app.analysis.fit import FitConfig, classify_job
    from app.analysis.keywords import analyze_jd

    jd = analyze_jd(SALES_JD)
    jd.update({"title": "Sales Engineer", "location": "", "role_category": "",
               "description_excerpt": SALES_JD})
    profile = {"target_roles": ["Backend Engineer"], "skills_demonstrated": ["python"],
               "skills_claimed": [], "experience": [], "projects": [],
               "education": [], "excluded_roles": ["sales"], "preferences": {}}
    assert classify_job(jd, profile, FitConfig())["classification"] == "poor"


def test_parse_category_from_doc_warnings():
    ok_doc = {"sections": {"experience": "Built Python APIs"}, "warnings": []}
    out = analyze_ats_v2(RESUME, ENG_JD, parsed_doc=ok_doc)
    assert out["categories"]["parse"]["score"] == 100.0
    bad_doc = {"sections": {}, "warnings": ["encrypted PDF: password required"]}
    out2 = analyze_ats_v2(RESUME, ENG_JD, parsed_doc=bad_doc)
    assert out2["categories"]["parse"]["score"] == 0.0
    assert any("Document blocker" in b for b in out2["blockers"])
    out3 = analyze_ats_v2(RESUME, ENG_JD, parsed_doc=None)
    assert out3["categories"]["parse"]["score"] is None  # legacy: unknown, not zero


def test_split_requirements():
    req, pref = split_requirements("Requirements: Python.\nPreferred: Go, Rust.")
    assert "python" in req and "go" in pref and "python" not in pref


def test_ats_v2_route_end_to_end(client, auth_headers):
    rid = client.post("/api/resumes",
                      files={"file": ("r.txt", RESUME.encode(), "text/plain")},
                      headers=auth_headers).json()["id"]
    aid = client.post("/api/applications", json={"company": "E", "role": "R", "raw_jd": ENG_JD},
                      headers=auth_headers).json()["id"]
    r = client.post(f"/api/applications/{aid}/ats-v2", json={"resume_id": rid},
                    headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["breakdown"]["ats_version"] == 2
    assert body["breakdown"]["categories"]["parse"]["score"] is not None  # real parsed_doc used
    assert client.get(f"/api/applications/{aid}", headers=auth_headers).json()["application"]["ats_score"] == body["score"]
    # custom weights honored
    r2 = client.post(f"/api/applications/{aid}/ats-v2",
                     json={"resume_id": rid, "weights": {"skills": 1.0}},
                     headers=auth_headers)
    assert r2.status_code == 201
    assert set(r2.json()["breakdown"]["weights"]) == {"skills"}
    assert client.post(f"/api/applications/{aid}/ats-v2", json={"resume_id": rid, "weights": {}},
                       headers=auth_headers).status_code == 400
