"""Learning Hub tests: plans, answers, progress, isolation."""

RESUME = "Sam\nEXPERIENCE\n- Built Python APIs\n\nSKILLS\nPython"
JD = "Backend role. Requirements: Python, Docker, Kubernetes. 2+ years."


def _app(client, auth_headers, jd=JD):
    return client.post("/api/applications", json={"company": "L", "role": "R", "raw_jd": jd},
                       headers=auth_headers).json()["id"]


def test_plan_orders_missing_first_and_marks_known(client, auth_headers):
    rid = client.post("/api/resumes", files={"file": ("r.txt", RESUME.encode(), "text/plain")},
                      headers=auth_headers).json()["id"]
    aid = _app(client, auth_headers)
    r = client.post("/api/learn/plans", json={"application_id": aid, "resume_id": rid},
                    headers=auth_headers)
    assert r.status_code == 201, r.text
    topics = r.json()["topics"]
    assert topics
    assert topics[0]["known"] is False  # missing JD terms first
    py = next(t for t in topics if t["term"] == "python")
    assert py["known"] is True and py["resume_evidence"]
    assert all({"levels", "exercises", "check", "progress"} <= set(t) for t in topics)


def test_correct_answer_masters_topic(client, auth_headers):
    aid = _app(client, auth_headers)
    pid = client.post("/api/learn/plans", json={"application_id": aid},
                      headers=auth_headers).json()["id"]
    topic = client.get(f"/api/learn/plans/{pid}", headers=auth_headers).json()["topics"][0]
    good = " ".join(p.replace("definition of ", "it is ").replace("use case for ", "used for ")
                     for p in topic["check"]["expected_points"])
    r = client.post(f"/api/learn/plans/{pid}/answer",
                    json={"topic": topic["term"], "answer": good}, headers=auth_headers)
    assert r.status_code == 200, r.text
    assert r.json()["verdict"] == "correct"
    assert r.json()["progress"]["status"] == "mastered"


def test_weak_answer_needs_revision_and_persists(client, auth_headers):
    aid = _app(client, auth_headers)
    pid = client.post("/api/learn/plans", json={"application_id": aid},
                      headers=auth_headers).json()["id"]
    topic = client.get(f"/api/learn/plans/{pid}", headers=auth_headers).json()["topics"][0]
    r = client.post(f"/api/learn/plans/{pid}/answer",
                    json={"topic": topic["term"], "answer": "I don't know yet."},
                    headers=auth_headers)
    assert r.json()["verdict"] == "needs_revision"
    assert r.json()["missed"]
    again = client.get(f"/api/learn/plans/{pid}", headers=auth_headers).json()
    node = next(t for t in again["topics"] if t["term"] == topic["term"])
    assert node["progress"]["status"] == "needs_revision"
    assert node["progress"]["attempts"] == 1


def test_answer_validation(client, auth_headers):
    aid = _app(client, auth_headers)
    pid = client.post("/api/learn/plans", json={"application_id": aid},
                      headers=auth_headers).json()["id"]
    assert client.post(f"/api/learn/plans/{pid}/answer",
                       json={"topic": "nope", "answer": "x"}, headers=auth_headers).status_code == 400
    assert client.post(f"/api/learn/plans/{pid}/answer",
                       json={"topic": "python", "answer": "  "}, headers=auth_headers).status_code == 400
    assert client.patch(f"/api/learn/plans/{pid}/topics",
                        json={"topic": "python", "status": "bogus"},
                        headers=auth_headers).status_code == 400
    assert client.get("/api/learn/plans/nope", headers=auth_headers).status_code == 404


def test_plan_isolation_and_listing(client, auth_headers):
    aid = _app(client, auth_headers)
    pid = client.post("/api/learn/plans", json={"application_id": aid},
                      headers=auth_headers).json()["id"]
    t2 = client.post("/api/auth/register", json={"username": "learner2", "password": "password123"}).json()["access_token"]
    h2 = {"Authorization": f"Bearer {t2}"}
    assert client.get(f"/api/learn/plans/{pid}", headers=h2).status_code == 404
    assert client.get("/api/learn/plans", headers=h2).json() == []
    mine = client.get("/api/learn/plans", headers=auth_headers).json()
    assert any(p["id"] == pid for p in mine)


def test_plan_requires_jd(client, auth_headers):
    aid = client.post("/api/applications", json={"company": "N", "role": "R"},
                      headers=auth_headers).json()["id"]
    assert client.post("/api/learn/plans", json={"application_id": aid},
                       headers=auth_headers).status_code == 400
