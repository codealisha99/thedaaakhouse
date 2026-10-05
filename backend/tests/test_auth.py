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


def test_users_cannot_see_each_others_data(client):
    t1 = client.post("/api/auth/register", json={"username": "user1", "password": "password123"}).json()["access_token"]
    t2 = client.post("/api/auth/register", json={"username": "user2", "password": "password123"}).json()["access_token"]
    h1, h2 = {"Authorization": f"Bearer {t1}"}, {"Authorization": f"Bearer {t2}"}
    app_id = client.post("/api/applications", json={"company": "Acme", "role": "Eng"}, headers=h1).json()["id"]
    assert client.get(f"/api/applications/{app_id}", headers=h2).status_code == 404
    assert client.get("/api/applications", headers=h2).json() == []
