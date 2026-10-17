"""Step 04 — opportunity ranking and startup prospects.

Acceptance covered here:
- eligibility, fit and competition evidence stay separate
- a no-vacancy prospect saves without a fake job description
- saving twice creates exactly one application
- exclusions win over scores
- missing / unlike competition measurements are not misleadingly compared
"""

AI_JOB = {
    "title": "Senior AI Engineer",
    "company_name": "Acme AI",
    "raw_text": (
        "Senior AI Engineer. You will build RAG pipelines and LLM agents. "
        "Requirements: 3+ years Python, FastAPI, vector databases (pgvector), Docker."
    ),
    "location": "Remote",
}

PROSPECT_URL = "https://startup-example.com"


def _profile(client, h, **kw):
    base = {"target_roles": ["AI Engineer"],
            "skills_demonstrated": ["python", "rag", "fastapi"],
            "experience": [{"title": "AI Engineer", "org": "X", "years": 3}]}
    base.update(kw)
    r = client.put("/api/profile", json=base, headers=h)
    assert r.status_code == 200, r.text
    return r.json()


def _job(client, h, **kw):
    body = dict(AI_JOB)
    body.update(kw)
    r = client.post("/api/jobs", json=body, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _weights(**kw):
    w = {"fit": 0.7, "freshness": 0.2, "opportunity": 0.1}
    w.update(kw)
    return w


# ---- creation + evaluation separation ----

def test_vacancy_creation_evaluates_separate_outputs(client, auth_headers):
    _profile(client, auth_headers)
    jid = _job(client, auth_headers)
    r = client.post("/api/opportunities", json={"job_id": jid}, headers=auth_headers)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["kind"] == "vacancy" and b["has_listing"] is True
    assert b["title"] == "Senior AI Engineer"
    ev = b["evaluation"]
    assert ev["eligibility"]["status"] == "eligible"
    assert ev["fit"]["classification"] == "target"
    assert ev["fit"]["score"] >= 0.65
    assert ev["competition"]["status"] == "missing"  # no observation → unknown, not zero
    assert ev["priority"]["score"] is not None
    factors = {c["factor"] for c in ev["priority"]["contributions"]}
    assert factors == {"fit", "freshness", "opportunity"}


def test_vacancy_creation_requires_existing_job(client, auth_headers):
    r = client.post("/api/opportunities", json={"job_id": "nope"}, headers=auth_headers)
    assert r.status_code == 404


def test_prospect_has_no_synthetic_jd(client, auth_headers):
    _profile(client, auth_headers)
    r = client.post("/api/opportunities/startups",
                    json={"url": PROSPECT_URL}, headers=auth_headers)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["kind"] == "startup_prospect" and b["has_listing"] is False
    assert b["title"] is None and b["description"] is None
    assert b["organization"]["domain"] == "startup-example.com"
    assert b["organization"]["name"] is None  # never invented
    assert b["source_evidence"][0]["method"] == "user_supplied"
    ev = b["evaluation"]
    # No JD: fit and JD-derived eligibility stay unknown, never guessed.
    assert ev["fit"]["classification"] == "needs_review"
    assert ev["fit"]["score"] == 0.0
    fit_excluded = next(e for e in ev["priority"]["coverage"]["excluded_factors"]
                        if e["factor"] == "fit")
    assert "No vacancy listing" in fit_excluded["reason"]
    checks = {c["key"]: c["status"] for c in ev["eligibility"]["checks"]}
    assert checks["experience_requirement"] == "unknown"
    assert ev["eligibility"]["status"] == "unknown"
    # Proxies are labeled, not counts.
    assert all(s["kind"] == "proxy" for s in ev["signals"])
    assert b["potentially_overlooked"] is True
    # Fit excluded from priority; formula renormalizes over available factors.
    excluded = [e["factor"] for e in ev["priority"]["coverage"]["excluded_factors"]]
    assert "fit" in excluded
    assert ev["priority"]["score"] is not None


def test_prospect_rejects_bad_url(client, auth_headers):
    assert client.post("/api/opportunities/startups", json={"url": "ftp://x"},
                       headers=auth_headers).status_code == 400
    assert client.post("/api/opportunities/startups", json={"url": "notaurl"},
                       headers=auth_headers).status_code == 400


# ---- the done criteria ----

def test_saving_prospect_creates_no_fake_description(client, auth_headers):
    _profile(client, auth_headers)
    oid = client.post("/api/opportunities/startups",
                      json={"url": PROSPECT_URL}, headers=auth_headers).json()["id"]
    r = client.post(f"/api/opportunities/{oid}/save", headers=auth_headers)
    assert r.status_code == 201, r.text
    b = r.json()
    assert b["created"] is True
    assert b["application"]["has_listing"] is False
    assert b["application"]["raw_jd"] == ""  # empty — never a synthetic JD
    assert b["application"]["company"] == "" or b["application"]["company"]
    assert b["application"]["job_url"] == PROSPECT_URL  # company site, not a job URL


def test_saving_twice_creates_one_application(client, auth_headers):
    _profile(client, auth_headers)
    jid = _job(client, auth_headers)
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    first = client.post(f"/api/opportunities/{oid}/save", headers=auth_headers)
    second = client.post(f"/api/opportunities/{oid}/save", headers=auth_headers)
    assert first.status_code == 201 and first.json()["created"] is True
    assert second.status_code == 200 and second.json()["created"] is False
    assert first.json()["application"]["id"] == second.json()["application"]["id"]
    apps = client.get("/api/applications", headers=auth_headers).json()
    assert len(apps) == 1
    assert apps[0]["company"] == "Acme AI"
    assert "RAG" in apps[0]["raw_jd"]


def test_saving_vacancy_links_job_and_description(client, auth_headers):
    _profile(client, auth_headers)
    jid = _job(client, auth_headers)
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    r = client.post(f"/api/opportunities/{oid}/save", headers=auth_headers)
    assert r.json()["application"]["has_listing"] is True
    assert "RAG" in r.json()["application"]["raw_jd"]
    detail = client.get(f"/api/opportunities/{oid}", headers=auth_headers).json()
    assert detail["application"]["status"] == "saved"


# ---- exclusions win over scores ----

def test_profile_exclusion_marks_ineligible(client, auth_headers):
    _profile(client, auth_headers, excluded_roles=["sales"])
    jid = _job(client, auth_headers, title="Sales Engineer", company_name="Acme AI",
               raw_text="Sales Engineer. Python demos. Requirements: 2+ years Python, Docker.")
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    detail = client.get(f"/api/opportunities/{oid}", headers=auth_headers).json()
    assert detail["eligibility"]["status"] == "ineligible"
    assert any("exclusion" in r.lower() for r in detail["evaluation"]["eligibility"]["reasons"])
    assert any("exclusion" in c for c in detail["evaluation"]["fit"]["conflicts"])


def test_eligibility_conflict_beats_high_fit_score(client, auth_headers):
    """Fit says target (it scores the JD); the remote-preference conflict is an
    eligibility violation the fit engine never sees. Eligibility wins."""
    _profile(client, auth_headers, preferences={"remote": True})
    jid = _job(client, auth_headers, location="New York, NY (on-site)",
               raw_text="AI Engineer. Build RAG pipelines with Python. Requirements: 3+ years Python, FastAPI, Docker.")
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    detail = client.get(f"/api/opportunities/{oid}", headers=auth_headers).json()
    assert detail["evaluation"]["fit"]["classification"] == "target"
    assert detail["evaluation"]["fit"]["score"] >= 0.65
    assert detail["eligibility"]["status"] == "ineligible"
    checks = {c["key"]: c for c in detail["evaluation"]["eligibility"]["checks"]}
    assert checks["work_mode"]["status"] == "violated"
    assert any("on-site" in r for r in detail["evaluation"]["eligibility"]["reasons"])


def test_explicit_exclusion_filters_and_blocks_save(client, auth_headers):
    _profile(client, auth_headers)
    jid = _job(client, auth_headers)
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    client.patch(f"/api/opportunities/{oid}/exclude",
                 json={"excluded": True, "reason": "not a fit"}, headers=auth_headers)
    # Excluded opportunities are hidden from the default listing...
    assert all(i["id"] != oid for i in
               client.get("/api/opportunities", headers=auth_headers).json()["items"])
    # ... but visible on request, and saving is blocked.
    items = client.get("/api/opportunities?include_excluded=true",
                       headers=auth_headers).json()["items"]
    assert any(i["id"] == oid for i in items)
    assert client.post(f"/api/opportunities/{oid}/save",
                       headers=auth_headers).status_code == 409
    # Unexclude restores listing + saving.
    client.patch(f"/api/opportunities/{oid}/exclude",
                 json={"excluded": False}, headers=auth_headers)
    assert any(i["id"] == oid for i in
               client.get("/api/opportunities", headers=auth_headers).json()["items"])
    assert client.post(f"/api/opportunities/{oid}/save",
                       headers=auth_headers).status_code == 201


# ---- competition evidence ----

def test_missing_competition_is_unknown_not_zero(client, auth_headers):
    _profile(client, auth_headers)
    jid = _job(client, auth_headers)
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    detail = client.get(f"/api/opportunities/{oid}", headers=auth_headers).json()
    assert detail["competition"]["status"] == "missing"
    assert detail["competition"]["observed_count"] is None
    # A missing count never qualifies as "lower observed competition".
    items = client.get("/api/opportunities?competition=lower_observed&max_applicants=50",
                       headers=auth_headers).json()["items"]
    assert all(i["id"] != oid for i in items)


def test_observed_count_qualifies_with_provenance(client, auth_headers):
    _profile(client, auth_headers)
    jid = _job(client, auth_headers)
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    r = client.post(f"/api/opportunities/{oid}/applicant-count",
                    json={"count": 12, "platform": "lever",
                          "source": "https://api.example.co/api/v0/postings/abc",
                          "meaning": "completed_applications"}, headers=auth_headers)
    assert r.status_code == 201, r.text
    obs = r.json()["observation"]
    assert obs["comparable"] is True
    detail = client.get(f"/api/opportunities/{oid}", headers=auth_headers).json()
    comp = detail["competition"]
    assert comp["status"] == "observed" and comp["observed_count"] == 12
    assert comp["meaning"] == "completed_applications"
    assert comp["comparable"] is True and comp["platform"] == "lever"
    items = client.get("/api/opportunities?competition=lower_observed&max_applicants=50",
                       headers=auth_headers).json()["items"]
    assert any(i["id"] == oid for i in items)
    # Threshold respects the count: 12 applicants is not <= 5.
    items = client.get("/api/opportunities?competition=lower_observed&max_applicants=5",
                       headers=auth_headers).json()["items"]
    assert all(i["id"] != oid for i in items)


def test_clicks_are_not_applications(client, auth_headers):
    _profile(client, auth_headers)
    jid = _job(client, auth_headers)
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    r = client.post(f"/api/opportunities/{oid}/applicant-count",
                    json={"count": 3, "platform": "jobboard", "meaning": "apply_clicks"},
                    headers=auth_headers)
    obs = r.json()["observation"]
    assert obs["comparable"] is False  # recorded, but not an applicant count
    items = client.get("/api/opportunities?competition=lower_observed&max_applicants=50",
                       headers=auth_headers).json()["items"]
    assert all(i["id"] != oid for i in items)


def test_unlike_platforms_not_compared_as_equal(client, auth_headers):
    """A Lever count and a LinkedIn count are different measurements; the
    'lower observed' filter only returns per-opportunity evidence with its own
    provenance attached — never a cross-platform leaderboard."""
    _profile(client, auth_headers)
    jid = _job(client, auth_headers)
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    client.post(f"/api/opportunities/{oid}/applicant-count",
                json={"count": 8, "platform": "linkedin", "meaning": "applicants"},
                headers=auth_headers)
    items = client.get("/api/opportunities?competition=lower_observed&max_applicants=50",
                       headers=auth_headers).json()["items"]
    row = next(i for i in items if i["id"] == oid)
    assert row["competition"]["platform"] == "linkedin"
    assert row["competition"]["meaning"] == "applicants"


# ---- weights, versioning, filters ----

def test_weights_validated(client, auth_headers):
    _profile(client, auth_headers)
    jid = _job(client, auth_headers)
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    assert client.post(f"/api/opportunities/{oid}/evaluate",
                       json={"weights": {"fit": -0.5, "freshness": 1, "opportunity": 0}},
                       headers=auth_headers).status_code == 400
    assert client.post(f"/api/opportunities/{oid}/evaluate",
                       json={"weights": {"fit": 0, "freshness": 0, "opportunity": 0}},
                       headers=auth_headers).status_code == 400
    r = client.post(f"/api/opportunities/{oid}/evaluate",
                    json={"weights": _weights(fit=1.0, freshness=0, opportunity=0)},
                    headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["config"]["weights"]["fit"] == 1.0
    # Each evaluate call versions the snapshot.
    assert r.json()["evaluation_no"] >= 2  # creation already wrote version 1
    hist = client.get(f"/api/opportunities/{oid}", headers=auth_headers).json()
    assert hist["evaluation"]["evaluation_no"] == r.json()["evaluation_no"]


def test_list_filters_kind_eligibility_fit(client, auth_headers):
    _profile(client, auth_headers)
    jid = _job(client, auth_headers)
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    sid = client.post("/api/opportunities/startups",
                      json={"url": PROSPECT_URL}, headers=auth_headers).json()["id"]
    all_items = client.get("/api/opportunities", headers=auth_headers).json()["items"]
    assert {i["kind"] for i in all_items} == {"vacancy", "startup_prospect"}
    assert len(client.get("/api/opportunities?kind=vacancy",
                         headers=auth_headers).json()["items"]) == 1
    assert len(client.get("/api/opportunities?eligibility=eligible",
                         headers=auth_headers).json()["items"]) == 1
    assert len(client.get("/api/opportunities?fit=target",
                         headers=auth_headers).json()["items"]) == 1
    assert any(i["id"] == sid for i in client.get(
        "/api/opportunities?competition=missing",
        headers=auth_headers).json()["items"])


def test_list_cursor_is_deterministic(client, auth_headers):
    _profile(client, auth_headers)
    ids = []
    for i in range(3):
        jid = _job(client, auth_headers, company_name=f"Co{i}",
                   raw_text=f"AI Engineer role number {i}. Python, RAG, FastAPI. 3+ years.")
        ids.append(client.post("/api/opportunities", json={"job_id": jid},
                               headers=auth_headers).json()["id"])
    page1 = client.get("/api/opportunities?limit=2", headers=auth_headers).json()
    assert len(page1["items"]) == 2 and page1["next_cursor"]
    page2 = client.get(f"/api/opportunities?limit=2&cursor={page1['next_cursor']}",
                       headers=auth_headers).json()
    assert len(page2["items"]) == 1
    assert page2["next_cursor"] is None
    paged = [i["id"] for i in page1["items"] + page2["items"]]
    assert sorted(paged) == sorted(ids)  # no overlap, no loss


# ---- ownership ----

def test_ownership_is_scoped(client, auth_headers):
    _profile(client, auth_headers)
    jid = _job(client, auth_headers)
    oid = client.post("/api/opportunities", json={"job_id": jid},
                      headers=auth_headers).json()["id"]
    t2 = client.post("/api/auth/register",
                     json={"username": "oppother", "password": "password123"}).json()["access_token"]
    h2 = {"Authorization": f"Bearer {t2}"}
    assert client.get(f"/api/opportunities/{oid}", headers=h2).status_code == 404
    assert client.get("/api/opportunities", headers=h2).json()["items"] == []
    assert client.post(f"/api/opportunities/{oid}/save", headers=h2).status_code == 404
    assert client.patch(f"/api/opportunities/{oid}/exclude",
                        json={"excluded": True}, headers=h2).status_code == 404


def test_startup_provider_registry_honest_default(client, auth_headers):
    r = client.get("/api/opportunities/providers", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["configured"] == "none"
    assert "none" in r.json()["available"]
    r = client.post("/api/opportunities/startups/search",
                    json={"query": "fintech"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["leads"] == [] and r.json()["provider"] == "none"
