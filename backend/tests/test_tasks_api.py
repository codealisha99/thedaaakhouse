"""HTTP surface of the durable tasks API — 202/poll/409/cancel, owner scoping."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.workflows.executor import execute, publish_pending_outbox
from app.workflows.handlers import register, TaskFailure

PROBE_KIND = "api.probe_send"
_holder = {"used": 0}


def _probe(payload, ctx):
    _holder["used"] += 1
    raise TaskFailure("api_probe_injected", "probe must run, only engine grant matters")  # pragma: no cover


register(PROBE_KIND, external_side_effect=True, summary="test-only side-effecting action")(_probe)


@pytest.fixture()
def db(client):
    """Session bound to the same sqlite file the app fixture created (runtime settings)."""
    from app.core.config import get_settings

    eng = create_engine(get_settings().database_url, connect_args={"check_same_thread": False})
    S = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    return S()


def _token(client, username):
    return client.post("/api/auth/register", json={"username": username, "password": "password123"}).json()["access_token"]


def _post(client, token, payload, headers=None):
    h = {"Authorization": f"Bearer {token}"}
    if headers:
        h.update(headers)
    return client.post("/api/tasks", json=payload, headers=h)


def test_enqueue_poll_contract_and_202(client):
    token = _token(client, "alice")
    r = _post(client, token, {"kind": "diagnostics.echo", "payload": {"message": "hi"}})
    assert r.status_code == 202, r.json()
    body = r.json()
    assert set(body) >= {"task_id", "status", "poll_url"}
    assert body["status"] == "queued"
    assert body["poll_url"].endswith(body["task_id"])

    poll = client.get(body["poll_url"], headers={"Authorization": f"Bearer {token}"})
    assert poll.status_code == 200
    assert poll.json()["id"] == body["task_id"]


def test_idempotency_header_replay_and_conflict(client):
    token = _token(client, "alice")
    headers = {"Idempotency-Key": "edge-1"}
    r1 = _post(client, token, {"kind": "diagnostics.echo", "payload": {"message": "x"}}, headers)
    r2 = _post(client, token, {"kind": "diagnostics.echo", "payload": {"message": "x"}}, headers)
    assert r1.status_code == 202 and r2.status_code == 202
    assert r2.json()["task_id"] == r1.json()["task_id"]

    r3 = _post(client, token, {"kind": "diagnostics.echo", "payload": {"message": "y"}}, headers)
    assert r3.status_code == 409
    assert "existing_task_id" in r3.json()["detail"]


def test_unknown_and_sideeffect_kinds_rejected(client):
    token = _token(client, "alice")
    assert _post(client, token, {"kind": "no.such", "payload": {}}).status_code == 422
    r = _post(client, token, {"kind": PROBE_KIND, "payload": {"marker": "m"}})
    assert r.status_code in {422, 403}


def test_owner_scoped_404_and_cancel(client, db):
    alice = _token(client, "alice")
    bob = _token(client, "bob")
    task_id = _post(client, alice, {"kind": "diagnostics.echo", "payload": {"message": "hi"}}).json()["task_id"]

    assert client.get(f"/api/tasks/{task_id}", headers={"Authorization": f"Bearer {bob}"}).status_code == 404
    assert client.post(f"/api/tasks/{task_id}/cancel", headers={"Authorization": f"Bearer {bob}"}).status_code == 404

    cancel = client.post(f"/api/tasks/{task_id}/cancel", headers={"Authorization": f"Bearer {alice}"})
    assert cancel.status_code == 200
    assert client.get(f"/api/tasks/{task_id}", headers={"Authorization": f"Bearer {alice}"}).json()["status"] == "cancelled"

    # cancelled tasks are never executed even when the dispatcher loses delivery constraints
    assert execute(db, task_id)["outcome"] == "skipped"


def test_full_pipeline_over_http_and_endpoint_shows_result(client, db):
    token = _token(client, "alice")
    body = _post(client, token, {"kind": "diagnostics.echo", "payload": {"message": "done"}}).json()
    task_id = body["task_id"]

    # dispatcher pass: publish outbox (default no-op publisher), worker pass: execute
    publish_pending_outbox(db)
    result = execute(db, task_id)
    assert result["outcome"] == "succeeded", result

    poll = client.get(body["poll_url"], headers={"Authorization": f"Bearer {token}"})
    assert poll.status_code == 200
    data = poll.json()
    assert data["status"] == "succeeded"
    assert data["result"]["echo"] == "done"


def test_task_health_reports_counts(client):
    token = _token(client, "alice")
    r = client.get("/api/tasks/health", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and "tasks" in r.json() and "pending_outbox_events" in r.json()
