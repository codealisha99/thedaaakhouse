"""Offline Gmail delivery path regressions; provider calls are always mocked."""
from cryptography.fernet import Fernet
import base64
import httpx

from app.db import models
from app.outreach.delivery_models import EmailAccount, OutreachSend, OutreachSuppression
from app.outreach import gmail
from app.workflows.executor import execute
from app.workflows.models import ActionApproval


def _draft(client, headers):
    company = client.post("/api/opportunities/startups", json={"url": "https://mail.test", "name": "Mail Co"}, headers=headers)
    assert company.status_code == 201
    r = client.post("/api/outreach/drafts", json={"opportunity_id": company.json()["id"], "recipient_email": "person@mail.test"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _account(client, email="owner@gmail.test"):
    session = client.app.state.testing_sessionmaker()
    try:
        user = session.query(models.User).filter_by(username="tester").one()
        row = EmailAccount(user_id=user.id, provider="gmail", email=email,
            refresh_token_ciphertext="encrypted-fixture", status="connected", scopes=[])
        session.add(row); session.commit()
    finally: session.close()


def _enable_gmail(monkeypatch):
    monkeypatch.setenv("GMAIL_ENABLED", "true")
    from app.core.config import get_settings
    get_settings.cache_clear()


def _approve(client, headers, draft):
    payload = {"draft_id": draft["id"], "payload_sha256": draft["payload_sha256"]}
    response = client.post("/api/automation/approvals", headers=headers, json={
        "action_kind": "outreach.send", "payload": payload, "ttl_seconds": 900,
        "object_ref": {"draft_id": draft["id"]},
    })
    assert response.status_code == 201, response.text
    return payload


def test_gmail_connection_disabled_by_default(client, auth_headers):
    response = client.post("/api/integrations/gmail/connect", headers=auth_headers)
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"]


def test_approved_send_freezes_payload_and_reports_acceptance(client, auth_headers, monkeypatch):
    _enable_gmail(monkeypatch)
    draft = _draft(client, auth_headers); _account(client)
    payload = _approve(client, auth_headers, draft)
    calls = []
    monkeypatch.setattr(gmail, "_api", lambda *a, **kw: calls.append(kw) or {"id": "gmsg-1", "threadId": "thread-1"})
    queued = client.post(f"/api/outreach/drafts/{draft['id']}/send", headers={**auth_headers, "Idempotency-Key": "send-once"})
    assert queued.status_code == 202, queued.text
    session = client.app.state.testing_sessionmaker()
    try: result = execute(session, queued.json()["task_id"])
    finally: session.close()
    assert result["outcome"] == "succeeded"
    session = client.app.state.testing_sessionmaker()
    try:
        send = session.query(OutreachSend).one()
        assert send.status == "accepted"
        assert send.provider_message_id == "gmsg-1"
        assert send.payload_snapshot["payload_sha256"] == draft["payload_sha256"]
        assert send.payload_snapshot["recipient_email"] == "person@mail.test"
        assert calls and "raw" in calls[0]["json"]
    finally: session.close()


def test_ambiguous_timeout_is_recorded_unknown_and_never_retried(client, auth_headers, monkeypatch):
    _enable_gmail(monkeypatch)
    draft = _draft(client, auth_headers); _account(client); _approve(client, auth_headers, draft)
    calls = []
    def timeout(*args, **kwargs):
        calls.append(1)
        raise httpx.TimeoutException("fixture timeout")
    monkeypatch.setattr(gmail, "_api", timeout)
    queued = client.post(f"/api/outreach/drafts/{draft['id']}/send", headers={**auth_headers, "Idempotency-Key": "send-timeout"})
    assert queued.status_code == 202
    session = client.app.state.testing_sessionmaker()
    try: first = execute(session, queued.json()["task_id"])
    finally: session.close()
    assert first["outcome"] == "succeeded"
    # Executor rejects redelivery after terminal completion; no second provider call.
    session = client.app.state.testing_sessionmaker()
    try: duplicate = execute(session, queued.json()["task_id"])
    finally: session.close()
    assert duplicate["outcome"] == "skipped"
    assert calls == [1]
    assert client.get("/api/outreach/sends", headers=auth_headers).json()[0]["status"] == "unknown"


def test_suppression_blocks_send_before_task_creation(client, auth_headers):
    draft = _draft(client, auth_headers); _account(client); _approve(client, auth_headers, draft)
    session = client.app.state.testing_sessionmaker()
    try:
        user = session.query(models.User).filter_by(username="tester").one()
        session.add(OutreachSuppression(user_id=user.id, email="person@mail.test", reason="opt_out")); session.commit()
    finally: session.close()
    response = client.post(f"/api/outreach/drafts/{draft['id']}/send", headers={**auth_headers, "Idempotency-Key": "suppressed"})
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "recipient_suppressed"


def test_reply_and_opt_out_events_are_idempotent_and_suppress_recipient(client, auth_headers, monkeypatch):
    _enable_gmail(monkeypatch)
    draft = _draft(client, auth_headers); _account(client); _approve(client, auth_headers, draft)
    monkeypatch.setattr(gmail, "_api", lambda *a, **kw: {"id": "gmsg-2", "threadId": "thread-reply"})
    queued = client.post(f"/api/outreach/drafts/{draft['id']}/send", headers={**auth_headers, "Idempotency-Key": "send-reply"})
    session = client.app.state.testing_sessionmaker()
    try: assert execute(session, queued.json()["task_id"])["outcome"] == "succeeded"
    finally: session.close()
    body = base64.urlsafe_b64encode(b"Please unsubscribe me.").decode().rstrip("=")
    response = {"messages": [{"id": "reply-1", "payload": {
        "headers": [{"name": "From", "value": "person@mail.test"}, {"name": "Subject", "value": "Re: hello"}],
        "body": {}, "parts": [{"mimeType": "text/plain", "body": {"data": body}}],
    }}]}
    monkeypatch.setattr(gmail, "_api", lambda *a, **kw: response)
    session = client.app.state.testing_sessionmaker()
    try:
        user = session.query(models.User).filter_by(username="tester").one()
        assert gmail.sync_replies(session, user.id) == 1
        assert gmail.sync_replies(session, user.id) == 0
        assert session.query(OutreachSuppression).filter_by(email="person@mail.test", reason="opt_out").count() == 1
        assert session.query(OutreachSend).one().status == "replied"
    finally: session.close()


def test_token_ciphertext_is_authenticated_encryption(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv("GMAIL_TOKEN_ENCRYPTION_KEY", key)
    from app.core.config import get_settings
    get_settings.cache_clear()
    token = "refresh-token-fixture"
    cipher = gmail._fernet().encrypt(token.encode()).decode()
    assert token not in cipher
    assert gmail._fernet().decrypt(cipher.encode()).decode() == token
