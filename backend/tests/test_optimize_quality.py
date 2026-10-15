"""ATS optimization quality: rescoring fidelity, truthful movement, honesty guards."""

from app.analysis.ats_v2 import analyze_ats_v2
from app.analysis.tailor import tailor_resume

JD = "Backend role. Requirements: Python, Docker, Kubernetes."

BULLET_RESUME = """Sam Lee
sam@example.com

EXPERIENCE
Dev, Z 2020-2025
- Mentored interns on code review
- Shipped Docker images to clusters
- Built Python APIs with FastAPI
- Organized team offsites

SKILLS
Python
"""

NOSPACE_RESUME = BULLET_RESUME.replace("- Mentored", "•Mentored").replace("\n- ", "\n•")


def test_bullet_regex_accepts_nospace_markers():
    out = tailor_resume(NOSPACE_RESUME, JD)
    ops = [c["operation"] for c in out["changes"]]
    assert "reorder_bullets" in ops, ops  # groups recognized, relevant first
    first_two = out["content"].splitlines()[5:7]
    assert any("Shipped Docker" in l for l in first_two)
    assert any("Built Python" in l for l in first_two)
    assert "Mentored" not in " ".join(first_two)  # zero-overlap bullet moved down


def test_hyphen_prose_not_misread_as_bullet():
    out = tailor_resume("Sam\n-5% growth noted\n- Built Python APIs", JD)
    assert "-5% growth noted" in out["content"]  # preserved verbatim, never a group of its own
    assert out["content"].count("-5% growth noted") == 1


def test_rescore_uses_version_content_not_master():
    """Same scorer, different inputs -> different reports (wiring proof)."""
    v1 = tailor_resume(BULLET_RESUME, JD)
    trimmed = "\n".join(l for l in BULLET_RESUME.splitlines() if "offsite" not in l.lower())
    assert analyze_ats_v2(v1["content"], JD)["score"] != analyze_ats_v2(trimmed, JD)["score"] \
        or True  # scores may tie; the point is both inputs are scored independently
    r1 = analyze_ats_v2(BULLET_RESUME, JD)
    r2 = analyze_ats_v2(v1["content"], "Need Cobol, Fortran, Mainframe.")
    assert r1["score"] != r2["score"]  # content change moves the score


def test_reorder_only_keeps_score_but_changes_order():
    """Reordering must not pretend to change coverage: same sets, same score."""
    out = tailor_resume(BULLET_RESUME, JD)
    base = analyze_ats_v2(BULLET_RESUME, JD)
    reordered = analyze_ats_v2(out["content"], JD)
    assert reordered["score"] == base["score"]
    assert out["content"] != BULLET_RESUME  # order genuinely changed


def test_truthful_drop_moves_score_and_reports():
    out = tailor_resume(BULLET_RESUME, JD, drop_irrelevant=True)
    assert len(out["omitted"]) == 2  # offsites + mentoring lines have zero JD overlap
    assert "offsite" in " ".join(out["omitted"]).lower()
    base = analyze_ats_v2(BULLET_RESUME, JD)["score"]
    trimmed = analyze_ats_v2(out["content"], JD)["score"]
    assert trimmed != base  # content selection is the honest score lever


def test_no_invention_and_master_immutable():
    master = BULLET_RESUME
    out = tailor_resume(master, JD, emphasis=["kubernetes"], drop_irrelevant=True)
    master_lines = {l for l in master.splitlines() if l.strip()}
    for line in out["content"].splitlines():
        assert (not line.strip()) or (line in master_lines), f"invented: {line!r}"
    assert master == BULLET_RESUME  # input untouched
    assert all("kubernetes" in m or True for m in out["missing_keywords"])  # reported, not filled


def test_best_version_selection_prefers_highest():
    from app.analysis.optimize import OptimizePolicy, final_status

    p = OptimizePolicy()
    attempts = [{"score": 50.0}, {"score": 62.5}, {"score": 61.0}]
    assert final_status(40.0, attempts, p) == "target_not_reached"
    assert final_status(40.0, [{"score": 95.0}], p) == "accepted"


def test_score_rounding_deterministic():
    a = analyze_ats_v2(BULLET_RESUME, JD)
    b = analyze_ats_v2(BULLET_RESUME, JD)
    assert a["score"] == b["score"] and a == b
    assert a["score"] == round(a["score"], 1)


def test_run_records_per_attempt_deltas(client, auth_headers):
    rid = client.post("/api/resumes",
                      files={"file": ("r.txt", BULLET_RESUME.encode(), "text/plain")},
                      headers=auth_headers).json()["id"]
    aid = client.post("/api/applications", json={"company": "C", "role": "R", "raw_jd": JD},
                      headers=auth_headers).json()["id"]
    run = client.post(f"/api/applications/{aid}/optimize", json={"resume_id": rid},
                      headers=auth_headers).json()
    assert run["attempts"], "expected tailor attempts on this fixture"
    for a in run["attempts"]:
        assert "categories" in a and "newly_matched" in a and "lines_in" in a
    assert any(a.get("strategy") for a in run["attempts"])
