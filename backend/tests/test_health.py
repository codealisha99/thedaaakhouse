def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["app"] == "thedaaakhouse"


def test_ready_probes_database(client):
    r = client.get("/ready")
    assert r.status_code == 200
    assert r.json() == {"ready": True, "database": "sqlite"}
