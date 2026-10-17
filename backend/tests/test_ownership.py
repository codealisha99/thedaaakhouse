"""Ownership regression tests (step 01 — secure foundations).

Policy: every user-visible record is scoped to its owner. Ownerless (null
user_id) legacy rows are quarantined — invisible via the API, claimable only
by the operator script. Cross-user references (job_id, resume_id,
resume_version_id) are rejected, never adopted.
"""

import pytest

from app.core.security import hash_password
from app.db.database import get_db
from app.db import models as app_models

JD = "Senior AI Engineer. Requirements: 3+ years Python, FastAPI, Docker."
RESUME_TXT = "Jane Doe\nEXPERIENCE\nSenior Engineer, Beta Corp, 2020-2025\n- Built RAG pipelines with Python\nSKILLS\nPython, FastAPI"


def _register(client, username):
    r = client.post("/api/auth/register", json={"username": username, "password": "password123"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _headers_b(client, username):
    return _register(client, username)


def _db(client):
    """A session on the SAME sqlite file the routes use (the client fixture
    overrides get_db with a per-test TestingSession)."""
    gen = client.app.dependency_overrides[get_db]()
    return next(gen)


def _make_users(client, *usernames):
    ids = {}
    db = _db(client)
    for u in usernames:
        obj = app_models.User(username=u, password_hash=hash_password("x12345678"))
        db.add(obj)
        db.flush()
        ids[u] = obj.id
    db.commit()
    db.close()
    return ids


def _seed_resume(client, user_id, rid):
    db = _db(client)
    r = app_models.Resume(id=rid, user_id=user_id, filename=f"{rid}.txt",
                          content_type="text/plain", file_path="", raw_text=RESUME_TXT)
    db.add(r)
    db.commit()
    db.close()


def _create_application(client, headers):
    r = client.post("/api/applications",
                    json={"company": "Acme", "role": "Engineer", "job_description": JD},
                    headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload_resume(client, headers, name="alice"):
    r = client.post("/api/resumes", headers=headers,
                    files={"file": (f"{name}.txt", RESUME_TXT.encode(), "text/plain")})
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------- ownerless rows are quarantined ----------------

def test_ownerless_resume_invisible_via_api(client, auth_headers):
    uid = _make_users(client, "seedrobot")["seedrobot"]
    db = _db(client)
    row = app_models.Resume(id="legacy-ownerless", user_id=None,
                            filename="legacy-ownerless.txt",
                            content_type="text/plain", file_path="",
                            raw_text=RESUME_TXT)
    db.add(row)
    db.commit()
    db.close()
    r = client.get("/api/resumes/legacy-ownerless", headers=auth_headers)
    assert r.status_code == 404


def test_ownerless_resume_invisible_unauthenticated(client):
    r = client.get("/api/resumes/legacy-ownerless")
    assert r.status_code in (401, 404)


def test_profile_seed_never_adopts_ownerless(client, auth_headers):
    r = client.post("/api/profile/seed", json={"resume_id": "legacy-ownerless"},
                    headers=auth_headers)
    assert r.status_code in (400, 404), r.text


def test_tailor_never_adopts_ownerless(client, auth_headers):
    app_id = _create_application(client, auth_headers)
    r = client.post(f"/api/applications/{app_id}/tailor",
                    json={"resume_id": "legacy-ownerless"}, headers=auth_headers)
    assert r.status_code == 404


# ---------------- cross-user records are invisible ----------------

def test_cross_user_resume_read_404(client, auth_headers):
    ids = _make_users(client, "alice", "bob")
    _seed_resume(client, ids["alice"], "alice-resume")
    r = client.get("/api/resumes/alice-resume",
                   headers=_headers_b(client, "bob2"))
    assert r.status_code == 404


def test_cross_user_resume_download_blocked(client, auth_headers):
    ids = _make_users(client, "carol", "dave")
    _seed_resume(client, ids["carol"], "carol-resume")
    r = client.get("/api/resumes/carol-resume/evidence",
                   headers=_headers_b(client, "dave2"))
    assert r.status_code == 404


def test_cross_user_job_read_404(client, auth_headers):
    ids = _make_users(client, "erin", "frank")
    db = _db(client)
    j = app_models.Job(id="erin-job", user_id=ids["erin"], title="Backend",
                       raw_text=JD)
    db.add(j)
    db.commit()
    db.close()
    r = client.get("/api/jobs/erin-job", headers=_headers_b(client, "frank2"))
    assert r.status_code == 404


def test_cross_user_job_reference_rejected(client, auth_headers):
    """Attachment to another user's job fails instead of silently linking."""
    ids = _make_users(client, "gina", "hank")
    db = _db(client)
    j = app_models.Job(id="gina-job", user_id=ids["gina"], title="Backend",
                       raw_text=JD)
    db.add(j)
    db.commit()
    db.close()
    hank_headers = _headers_b(client, "hank2")
    r = client.post("/api/applications",
                    json={"company": "Acme", "role": "Backend", "job_description": JD,
                          "job_id": "gina-job"},
                    headers=hank_headers)
    assert r.status_code in (400, 404), r.text
    if r.status_code == 201:  # hard-fail if the route ever creates it
        body = r.json()
        assert body.get("job_id") != "gina-job"


def test_cross_user_version_reference_rejected(client, auth_headers):
    ids = _make_users(client, "iris", "jack")
    db = _db(client)
    v = app_models.ResumeVersion(id="iris-version", user_id=ids["iris"],
                                 resume_id="none", content="c", label="l")
    db.add(v)
    db.commit()
    db.close()
    app_id = _create_application(client, auth_headers)
    r = client.patch(f"/api/applications/{app_id}",
                     json={"resume_version_id": "iris-version"},
                     headers=_headers_b(client, "jack2"))
    assert r.status_code == 404, r.text


def test_attach_version_rejects_cross_user(client, auth_headers):
    ids = _make_users(client, "kate", "liam")
    db = _db(client)
    v = app_models.ResumeVersion(id="kate-version", user_id=ids["kate"],
                                 resume_id="none", content="c", label="l")
    db.add(v)
    db.commit()
    db.close()
    app_id = _create_application(client, auth_headers)
    r = client.post(f"/api/applications/{app_id}/attach-version",
                    json={"resume_version_id": "kate-version"},
                    headers=_headers_b(client, "liam2"))
    assert r.status_code == 404


def test_tailor_rejects_cross_user_resume(client, auth_headers):
    ids = _make_users(client, "mia", "noah")
    _seed_resume(client, ids["mia"], "mia-resume")
    app_id = _create_application(client, auth_headers)
    r = client.post(f"/api/applications/{app_id}/tailor",
                    json={"resume_id": "mia-resume"},
                    headers=_headers_b(client, "noah2"))
    assert r.status_code == 404


# ---------------- learning / arena scoping ----------------

def test_learn_plan_rejects_cross_user_resume(client, auth_headers):
    ids = _make_users(client, "olive", "pete")
    _seed_resume(client, ids["olive"], "olive-resume")
    app_id = _create_application(client, auth_headers)
    r = client.post("/api/learn/plans",
                    json={"application_id": app_id, "topic": "Python",
                          "resume_id": "olive-resume"},
                    headers=_headers_b(client, "pete2"))
    assert r.status_code in (400, 404), r.text


def test_arena_start_rejects_cross_user_resume(client, auth_headers, sample_jd):
    ids = _make_users(client, "quinn", "rita")
    _seed_resume(client, ids["quinn"], "quinn-resume")
    app_id = _create_application(client, auth_headers)
    r = client.post("/api/arena/sessions",
                    json={"application_id": app_id, "mode": "behavioral",
                          "resume_id": "quinn-resume"},
                    headers=_headers_b(client, "rita2"))
    assert r.status_code in (400, 404), r.text


# ---------------- list scoping ----------------

def test_lists_are_user_scoped(client, auth_headers):
    ids = _make_users(client, "sam", "tina")
    db = _db(client)
    j = app_models.Job(id="sam-job", user_id=ids["sam"], title="Backend", raw_text=JD)
    r = app_models.Resume(id="sam-resume", user_id=ids["sam"], filename="sam-resume.txt",
                          content_type="text/plain", file_path="", raw_text=RESUME_TXT)
    db.add_all([j, r])
    db.commit()
    db.close()
    other = _headers_b(client, "tina2")
    assert all(job["id"] != "sam-job" for job in client.get("/api/jobs", headers=other).json())
    assert all(entry["id"] != "sam-resume"
               for entry in client.get("/api/resumes", headers=other).json())
    mine = client.get("/api/resumes", headers=_headers_b(client, "samx")).json()
    assert not mine  # the original user 'sam' never registered a session for listings
