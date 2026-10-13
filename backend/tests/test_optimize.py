"""ATS optimization workflow tests: loop policy, honesty, LaTeX, safety."""

STRONG_RESUME = """Sam Lee
sam@example.com 555-0199

EXPERIENCE
Senior Backend Engineer, Z 2019-2025
- Built Python APIs with FastAPI serving 10k users daily
- Shipped Docker images to Kubernetes clusters on AWS
- Postgres query optimization cutting p99 latency

EDUCATION
BS Computer Science, 2015-2019

SKILLS
Python, FastAPI, Docker, Kubernetes, AWS, Postgres, SQL
"""
STRONG_JD = ("Senior Backend Engineer. Requirements: 4+ years Python, FastAPI, Docker, "
             "Kubernetes, AWS, Postgres. Education: BS in Computer Science.")
TRIVIAL_JD = "Need Python."
WEAK_JD = "Platform role. Requirements: Kubernetes, Terraform, Go, Rust, Postgres, Kafka. 5+ years."
WEAK_RESUME = "Sam\n- Built Python APIs\nSKILLS\nPython"


def _upload(client, h, text=STRONG_RESUME, name="r.txt", ctype="text/plain"):
    r = client.post("/api/resumes", files={"file": (name, text.encode(), ctype)}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _app(client, h, jd, **kw):
    p = {"company": "C", "role": "R", "raw_jd": jd}
    p.update(kw)
    return client.post("/api/applications", json=p, headers=h).json()["id"]


def _run(client, h, aid, rid, policy=None):
    body = {"resume_id": rid}
    if policy is not None:
        body["policy"] = policy
    return client.post(f"/api/applications/{aid}/optimize", json=body, headers=h)


def test_pure_policy_units():
    from app.analysis.optimize import OptimizePolicy, final_status, plan_next_attempt, should_stop

    p = OptimizePolicy()
    assert p.as_dict() == {"trigger_below": 90.0, "accept_at_least": 92.0, "max_attempts": 3}
    for bad in [{"trigger_below": 0}, {"accept_at_least": 101}, {"max_attempts": 11},
                {"trigger_below": 95, "accept_at_least": 90}]:
        try:
            OptimizePolicy(**bad).validate()
        except ValueError:
            continue
        raise AssertionError(f"bad policy accepted: {bad}")
    assert should_stop([50.0, 95.0], p) == (True, "acceptance threshold reached")
    assert should_stop([50.0, 60.0, 70.0, 80.0], p)[0] is True  # max attempts
    assert should_stop([50.0, 60.0, 60.0, 60.0], OptimizePolicy(max_attempts=9))[1].startswith("score plateaued")
    assert should_stop([50.0, 60.0], p) == (False, "")
    assert final_status(95.0, [], p) == "accepted"
    assert final_status(91.0, [], p) == "target_not_reached"
    assert final_status(50.0, [{"score": 95.0}], p) == "accepted"
    assert plan_next_attempt(1, [])["drop_irrelevant"] is False
    assert plan_next_attempt(3, ["x"])["drop_irrelevant"] is True


def test_low_score_triggers_loop_and_accepts(client, auth_headers):
    rid = _upload(client, auth_headers)
    aid = _app(client, auth_headers, STRONG_JD)
    r = _run(client, auth_headers, aid, rid)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["initial_score"] < 90.0
    assert len(body["attempts"]) >= 1
    assert body["status"] in ("accepted", "target_not_reached")
    assert body["final_score"] is not None
    assert body["latex_status"] == "valid"


def test_accepted_when_initial_meets_threshold(client, auth_headers):
    rid = _upload(client, auth_headers)
    aid = _app(client, auth_headers, TRIVIAL_JD)
    init = client.post(f"/api/applications/{aid}/ats-v2", json={"resume_id": rid},
                       headers=auth_headers).json()["score"]
    assert init >= 90.0
    # acceptance bar set exactly at the measured initial score: accepted, no tailor calls
    r = _run(client, auth_headers, aid, rid,
             policy={"trigger_below": 90.0, "accept_at_least": init, "max_attempts": 3})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["initial_score"] == init
    assert body["attempts"] == [] and body["status"] == "accepted"
    assert body["final_version_id"] is None  # no tailor call happened
    assert body["final_score"] == init


def test_band_no_tailor_without_acceptance(client, auth_headers):
    rid = _upload(client, auth_headers)
    aid = _app(client, auth_headers, TRIVIAL_JD)
    init = client.post(f"/api/applications/{aid}/ats-v2", json={"resume_id": rid},
                       headers=auth_headers).json()["score"]
    assert init >= 90.0
    # raise the bar above reach: no tailor runs, truthful non-acceptance
    r = _run(client, auth_headers, aid, rid,
             policy={"trigger_below": 90.0, "accept_at_least": 100.0, "max_attempts": 3})
    body = r.json()
    assert r.status_code == 201, r.text
    assert body["attempts"] == []
    assert body["status"] == "target_not_reached"


def test_three_failed_attempts_stay_honest(client, auth_headers):
    rid = _upload(client, auth_headers, WEAK_RESUME)
    aid = _app(client, auth_headers, WEAK_JD)
    r = _run(client, auth_headers, aid, rid)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["initial_score"] < 90.0
    assert len(body["attempts"]) == 3, body["attempts"]
    assert body["status"] == "target_not_reached"
    assert body["final_version_id"] is not None  # best version kept
    assert body["gaps"]  # remaining gaps explained


def test_master_never_modified_and_no_invention(client, auth_headers):
    rid = _upload(client, auth_headers)
    before = client.get(f"/api/resumes/{rid}", headers=auth_headers).json()["raw_text"]
    aid = _app(client, auth_headers, STRONG_JD)
    body = _run(client, auth_headers, aid, rid).json()
    after = client.get(f"/api/resumes/{rid}", headers=auth_headers).json()["raw_text"]
    assert before == after
    master_lines = {l for l in before.splitlines() if l.strip()}
    for att in body["attempts"]:
        v = client.get(f"/api/applications/versions/{att['version_id']}",
                       headers=auth_headers).json()
        for line in v["content"].splitlines():
            assert (not line.strip()) or (line in master_lines), f"invented line: {line!r}"


def test_latex_valid_escaped_and_saved(client, auth_headers):
    tricky = ("Sam % Lee\nsam@example.com & co\n\nEXPERIENCE\nDev, $BigCo_Inc 2020-2025\n"
              "- Grew revenue 100% with R&D\n\nSKILLS\nPython")
    rid = _upload(client, auth_headers, tricky)
    aid = _app(client, auth_headers, "Need Python.")
    body = _run(client, auth_headers, aid, rid).json()
    assert body["latex_status"] == "valid"
    run_id = body["id"]
    tex = client.get(f"/api/optimize/runs/{run_id}/latex", headers=auth_headers)
    assert tex.status_code == 200
    assert "\\documentclass" in tex.text and "\\%" in tex.text and "\\$" in tex.text
    assert "100%" not in tex.text  # raw % never leaks unescaped


def test_pdf_status_honest_without_toolchain(client, auth_headers):
    rid = _upload(client, auth_headers)
    aid = _app(client, auth_headers, TRIVIAL_JD)
    run_id = _run(client, auth_headers, aid, rid).json()["id"]
    r = client.get(f"/api/optimize/runs/{run_id}/pdf", headers=auth_headers)
    import shutil

    if shutil.which("pdflatex") is None:
        assert r.status_code == 404
        assert "tex" in r.json()["detail"].lower()
    else:
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"


def test_run_history_and_validation(client, auth_headers):
    rid = _upload(client, auth_headers)
    aid = _app(client, auth_headers, TRIVIAL_JD)
    run_id = _run(client, auth_headers, aid, rid).json()["id"]
    listed = client.get(f"/api/optimize/runs?application_id={aid}", headers=auth_headers).json()
    assert any(x["id"] == run_id for x in listed)
    one = client.get(f"/api/optimize/runs/{run_id}", headers=auth_headers).json()
    assert one["status"] in ("accepted", "target_not_reached") and "stop_reason" in one
    assert one["policy"]["max_attempts"] == 3
    assert client.get("/api/optimize/runs/nope", headers=auth_headers).status_code == 404


def test_optimize_errors_and_retry_safety(client, auth_headers):
    rid = _upload(client, auth_headers)
    aid = _app(client, auth_headers, STRONG_JD)
    assert _run(client, auth_headers, "nope", rid).status_code == 404
    assert _run(client, auth_headers, aid, "nope").status_code == 404
    assert client.post(f"/api/applications/{aid}/optimize", json={}, headers=auth_headers).status_code == 400
    bare = _app(client, auth_headers, "")
    assert _run(client, auth_headers, bare, rid).status_code in (201, 400)
    bad = _run(client, auth_headers, aid, rid, policy={"max_attempts": 99}).status_code
    assert bad == 400
    n0 = len(client.get("/api/applications/versions/all", headers=auth_headers).json())
    _run(client, auth_headers, aid, rid)
    _run(client, auth_headers, aid, rid)
    n1 = len(client.get("/api/applications/versions/all", headers=auth_headers).json())
    assert n1 >= n0  # retries only append versions; master untouched
    master = client.get(f"/api/resumes/{rid}", headers=auth_headers).json()["raw_text"]
    assert "Python" in master
