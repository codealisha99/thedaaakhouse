"""Career Fit Engine tests: classifications, constraints, overrides, compare."""

AI_JD = ("Senior AI Engineer. Build RAG pipelines and LLM agents with Python. "
         "Requirements: 3+ years Python, RAG, FastAPI, Docker.")
BACKEND_JD = ("Backend Engineer. Own Python services, Postgres, Docker, Kubernetes. "
              "Requirements: 2+ years Python, Docker.")
SALES_JD = ("Sales Engineer. Demo our Python-based platform to clients, travel 80%. "
            "Requirements: Python, Docker, presentations, travel.")
POOR_JD = "Sales Manager. Lead a regional team. Requirements: leadership, targets."
THIN_JD = "Great opportunity!!! Apply now!!!"
SENIOR_JD = ("Principal Engineer. Requirements: 10+ years Python, architecture.")


def _profile(client, h, **kw):
    base = {"target_roles": ["AI Engineer"], "skills_demonstrated": ["python", "rag", "fastapi"],
            "experience": [{"title": "AI Engineer", "org": "X", "years": 3}]}
    base.update(kw)
    r = client.put("/api/profile", json=base, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _app(client, h, jd, **kw):
    p = {"company": "C", "role": "R", "raw_jd": jd}
    p.update(kw)
    return client.post("/api/applications", json=p, headers=h).json()["id"]


def _eval(client, h, aid, weights=None):
    body = {"application_id": aid}
    if weights:
        body["weights"] = weights
    return client.post("/api/fit/evaluate", json=body, headers=h)


def test_profile_crud_and_provenance(client, auth_headers):
    r = client.put("/api/profile", json={"target_roles": ["ML Engineer"], "skills_claimed": ["go"]},
                   headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["target_roles"] == ["ML Engineer"]
    assert r.json()["provenance"]["target_roles"] == "user"
    assert client.get("/api/profile", headers=auth_headers).json()["skills_claimed"] == ["go"]


def test_seed_from_resume_marks_provenance(client, auth_headers):
    rid = client.post("/api/resumes",
                      files={"file": ("r.txt", b"Sam\n- Built Python APIs\nSKILLS\nPython, Docker", "text/plain")},
                      headers=auth_headers).json()["id"]
    r = client.post("/api/profile/seed", json={"resume_id": rid}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert "python" in r.json()["profile"]["skills_demonstrated"]
    assert r.json()["profile"]["provenance"]["skills_demonstrated"] == f"resume:{rid}"
    assert r.json()["evidence"]["python"]
    assert client.post("/api/profile/seed", json={"resume_id": "nope"},
                       headers=auth_headers).status_code == 404


def test_target_classification(client, auth_headers):
    _profile(client, auth_headers)
    aid = _app(client, auth_headers, AI_JD)
    r = _eval(client, auth_headers, aid)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["classification"] == "target" and b["recommendation"] == "prioritize"
    assert b["score"] >= 0.65 and b["factors"]["direction"] == 1.0
    assert any("target role" in x for x in b["reasons"])


def test_adjacent_backend_role(client, auth_headers):
    _profile(client, auth_headers)
    aid = _app(client, auth_headers, BACKEND_JD)
    b = _eval(client, auth_headers, aid).json()
    assert b["classification"] == "adjacent" and b["recommendation"] == "consider"


def test_poor_unrelated_role(client, auth_headers):
    _profile(client, auth_headers)
    aid = _app(client, auth_headers, POOR_JD)
    b = _eval(client, auth_headers, aid).json()
    assert b["classification"] == "poor" and b["recommendation"] == "exclude"


def test_exclusion_overrides_high_overlap(client, auth_headers):
    _profile(client, auth_headers, excluded_roles=["sales"])
    aid = _app(client, auth_headers, SALES_JD)
    b = _eval(client, auth_headers, aid).json()
    assert b["classification"] == "poor", b
    assert any("exclusion" in c for c in b["conflicts"])


def test_needs_review_on_thin_jd(client, auth_headers):
    _profile(client, auth_headers)
    aid = _app(client, auth_headers, THIN_JD)
    b = _eval(client, auth_headers, aid).json()
    assert b["classification"] == "needs_review" and b["recommendation"] == "review"


def test_experience_blocker_is_poor(client, auth_headers):
    _profile(client, auth_headers)
    aid = _app(client, auth_headers, SENIOR_JD)
    b = _eval(client, auth_headers, aid).json()
    assert b["classification"] == "poor"
    assert any("blocker" in c for c in b["conflicts"])


def test_evaluate_requires_jd_and_app(client, auth_headers):
    aid = client.post("/api/applications", json={"company": "N", "role": "R"},
                      headers=auth_headers).json()["id"]
    assert _eval(client, auth_headers, aid).status_code == 400
    assert _eval(client, auth_headers, "nope").status_code == 404


def test_override_recorded_without_changing_rules(client, auth_headers):
    _profile(client, auth_headers)
    aid = _app(client, auth_headers, POOR_JD)
    eid = _eval(client, auth_headers, aid).json()["id"]
    r = client.patch(f"/api/fit/evaluations/{eid}", json={"classification": "adjacent"},
                     headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["overridden"] is True and r.json()["classification"] == "adjacent"
    hist = client.get(f"/api/fit/history/{aid}", headers=auth_headers).json()
    assert hist[0]["overridden"] is True
    assert client.patch("/api/fit/evaluations/nope", json={"classification": "target"},
                        headers=auth_headers).status_code == 404
    assert client.patch(f"/api/fit/evaluations/{eid}", json={"classification": "nope"},
                        headers=auth_headers).status_code == 400


def test_custom_weights_accepted(client, auth_headers):
    _profile(client, auth_headers)
    aid = _app(client, auth_headers, AI_JD)
    r = _eval(client, auth_headers, aid, weights={"direction": 1.0, "tech_edu": 0, "transfer": 0, "progression": 0})
    assert r.status_code == 201
    assert r.json()["config"]["weights"]["direction"] == 1.0


def test_compare_lists_fit_and_ats(client, auth_headers):
    _profile(client, auth_headers)
    a1 = _app(client, auth_headers, AI_JD)
    a2 = _app(client, auth_headers, POOR_JD)
    _eval(client, auth_headers, a1)
    r = client.post("/api/fit/compare", json={"application_ids": [a1, a2, "nope"]},
                    headers=auth_headers)
    assert r.status_code == 200
    rows = {x["application_id"]: x for x in r.json()}
    assert rows[a1]["fit"]["classification"] == "target"
    assert rows[a2]["fit"] is None and rows[a2]["ats_score"] is None


def test_fit_isolation(client, auth_headers):
    _profile(client, auth_headers)
    aid = _app(client, auth_headers, AI_JD)
    eid = _eval(client, auth_headers, aid).json()["id"]
    t2 = client.post("/api/auth/register", json={"username": "fitx", "password": "password123"}).json()["access_token"]
    h2 = {"Authorization": f"Bearer {t2}"}
    assert client.get(f"/api/fit/history/{aid}", headers=h2).status_code == 404
    assert client.patch(f"/api/fit/evaluations/{eid}", json={"classification": "target"},
                        headers=h2).status_code == 404
    assert client.get("/api/profile", headers=h2).json()["target_roles"] == []
