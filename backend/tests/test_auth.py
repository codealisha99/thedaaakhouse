def test_register_login_me(client):
    r = client.post("/api/auth/register", json={"username": "alice", "password": "password123"})
    assert r.status_code == 201, r.text
    assert r.json()["username"] == "alice"

    r2 = client.post("/api/auth/login", json={"username": "alice", "password": "password123"})
    assert r2.status_code == 200
    token = r2.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "alice"


def test_duplicate_username_rejected(client):
    client.post("/api/auth/register", json={"username": "bob", "password": "password123"})
    r = client.post("/api/auth/register", json={"username": "bob", "password": "password123"})
    assert r.status_code == 400


def test_wrong_password_rejected(client):
    client.post("/api/auth/register", json={"username": "carol", "password": "password123"})
    r = client.post("/api/auth/login", json={"username": "carol", "password": "wrongpass1"})
    assert r.status_code == 401


def test_protected_routes_need_token(client):
    assert client.get("/api/applications").status_code == 401
    assert client.get("/api/resumes").status_code == 401


def test_production_guard_rejects_dev_secret(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    get_settings.cache_clear()
    try:
        with __import__("pytest").raises(RuntimeError, match="refusing to start"):
            get_settings().ensure_production_ready()
    finally:
        get_settings.cache_clear()


def test_production_guard_accepts_real_secret(monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("JWT_SECRET", "a-long-random-secret-value-for-tests-123")
    get_settings.cache_clear()
    try:
        get_settings().ensure_production_ready()  # must not raise
    finally:
        get_settings.cache_clear()


def test_expired_token_rejected(client, auth_headers):
    import time

    from app.core.config import get_settings
    from app.core.security import create_token

    token = create_token("nobody", get_settings().jwt_secret, expiry_min=0)
    time.sleep(0.05)
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


def test_tampered_token_rejected(client, auth_headers):
    token = auth_headers["Authorization"].split()[1]
    bad = token[:-2] + ("ab" if not token.endswith("ab") else "cd")
    r = client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"})
    assert r.status_code == 401


def test_rate_limiter_unit():
    from app.core.ratelimit import RateLimiter

    rl = RateLimiter(max_hits=3, window_s=60)
    assert all(rl.allow("k", now=1000.0 + i * 0.1) for i in range(3))
    assert not rl.allow("k", now=1000.4)
    assert rl.allow("k", now=1061.0)  # window slid
    assert rl.allow("other", now=1000.4)


def test_security_headers_present(client):
    r = client.get("/health")
    assert r.headers.get("x-content-type-options") == "nosniff"
    assert r.headers.get("x-frame-options") == "DENY"


def test_users_cannot_see_each_others_data(client):
    t1 = client.post("/api/auth/register", json={"username": "user1", "password": "password123"}).json()["access_token"]
    t2 = client.post("/api/auth/register", json={"username": "user2", "password": "password123"}).json()["access_token"]
    h1, h2 = {"Authorization": f"Bearer {t1}"}, {"Authorization": f"Bearer {t2}"}
    app_id = client.post("/api/applications", json={"company": "Acme", "role": "Eng"}, headers=h1).json()["id"]
    assert client.get(f"/api/applications/{app_id}", headers=h2).status_code == 404
    assert client.get("/api/applications", headers=h2).json() == []
