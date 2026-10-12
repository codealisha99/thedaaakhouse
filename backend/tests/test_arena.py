"""Interview Arena tests: modes, turns, adaptive follow-ups, summaries."""

JD = "Backend role. Requirements: Python, Docker, Kubernetes."
RESUME = "Sam\n- Built Python APIs with Docker\n\nSKILLS\nPython, Docker"


def _app_resume(client, auth_headers):
    rid = client.post("/api/resumes", files={"file": ("r.txt", RESUME.encode(), "text/plain")},
                      headers=auth_headers).json()["id"]
    aid = client.post("/api/applications", json={"company": "A", "role": "R", "raw_jd": JD},
                      headers=auth_headers).json()["id"]
    return aid, rid


def test_start_dsa_easy_caps_difficulty(client, auth_headers):
    r = client.post("/api/arena/sessions", json={"mode": "dsa", "difficulty": "easy"},
                    headers=auth_headers)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "active" and body["current"]
    assert all(q["difficulty"] == "easy" for q in [body["current"]] if "difficulty" in q)


def test_start_modes_and_validation(client, auth_headers):
    aid, rid = _app_resume(client, auth_headers)
    for mode in ["resume", "technical", "system_design", "cs", "aiml", "mock"]:
        r = client.post("/api/arena/sessions",
                        json={"mode": mode, "application_id": aid, "resume_id": rid},
                        headers=auth_headers)
        assert r.status_code == 201, (mode, r.text)
        assert r.json()["total"] > 0
    assert client.post("/api/arena/sessions", json={"mode": "nope"},
                       headers=auth_headers).status_code == 400
    assert client.post("/api/arena/sessions", json={"mode": "dsa", "difficulty": "nope"},
                       headers=auth_headers).status_code == 400
    # drill with no JD/resume context is honest about having nothing to work with
    assert client.post("/api/arena/sessions", json={"mode": "resume"},
                       headers=auth_headers).status_code == 400


def test_answer_flow_strong_then_weak(client, auth_headers):
    r = client.post("/api/arena/sessions", json={"mode": "dsa", "difficulty": "easy"},
                    headers=auth_headers).json()
    sid = r["id"]
    q1 = r["current"]
    good = " ".join(q1.get("points", [])) + " extra context words here"
    a1 = client.post(f"/api/arena/sessions/{sid}/answer", json={"answer": good},
                     headers=auth_headers)
    assert a1.status_code == 200, a1.text
    assert a1.json()["evaluation"]["verdict"] == "strong"
    assert a1.json()["evaluation"]["follow_up"] is None
    a2 = client.post(f"/api/arena/sessions/{sid}/answer", json={"answer": "no idea"},
                     headers=auth_headers)
    assert a2.json()["evaluation"]["verdict"] == "weak"
    assert a2.json()["evaluation"]["follow_up"]
    assert a2.json()["completed"] is False


def test_complete_session_yields_summary(client, auth_headers):
    r = client.post("/api/arena/sessions", json={"mode": "cs", "difficulty": "easy"},
                    headers=auth_headers).json()
    sid, total = r["id"], r["total"]
    assert total > 0
    last = None
    for _ in range(total):
        last = client.post(f"/api/arena/sessions/{sid}/answer",
                           json={"answer": "thorough correct answer with full detail"},
                           headers=auth_headers).json()
    assert last["completed"] is True
    assert last["summary"]["by_category"]
    fetched = client.get(f"/api/arena/sessions/{sid}", headers=auth_headers).json()
    assert fetched["status"] == "complete"
    assert fetched["average_score"] is not None
    # answering a finished session is rejected
    assert client.post(f"/api/arena/sessions/{sid}/answer", json={"answer": "x"},
                       headers=auth_headers).status_code == 400


def test_answer_validation(client, auth_headers):
    sid = client.post("/api/arena/sessions", json={"mode": "dsa"},
                      headers=auth_headers).json()["id"]
    assert client.post(f"/api/arena/sessions/{sid}/answer", json={"answer": "  "},
                       headers=auth_headers).status_code == 400
    assert client.get("/api/arena/sessions/nope", headers=auth_headers).status_code == 404


def test_arena_isolation_and_listing(client, auth_headers):
    sid = client.post("/api/arena/sessions", json={"mode": "dsa"},
                      headers=auth_headers).json()["id"]
    t2 = client.post("/api/auth/register", json={"username": "arenax", "password": "password123"}).json()["access_token"]
    h2 = {"Authorization": f"Bearer {t2}"}
    assert client.get(f"/api/arena/sessions/{sid}", headers=h2).status_code == 404
    assert client.get("/api/arena/sessions", headers=h2).json() == []
    assert any(s["id"] == sid for s in client.get("/api/arena/sessions", headers=auth_headers).json())
