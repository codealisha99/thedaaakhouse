"""Step 07 submission package and receipt acceptance paths."""

import httpx
import pytest

from app.core.config import get_settings
from app.db import models
from app.submissions.adapters import test_destination
from app.submissions.models import ApplicationSubmission
from app.workflows.executor import execute
from app.workflows.models import TaskRun


def _application_version(client, headers, company="Acme"):
    app = client.post("/api/applications", json={
        "company": company, "role": "Engineer", "job_url": "https://apply.test/form",
    }, headers=headers)
    assert app.status_code == 201, app.text
    app_id = app.json()["id"]
    session = client.app.state.testing_sessionmaker()
    try:
        user = session.query(models.User).filter_by(username="tester").one()
        version = models.ResumeVersion(
            user_id=user.id, application_id=app_id, label="resume-v1",
            content="Jane Doe\nBuilt Python APIs serving 1000 users.",
        )
        session.add(version)
        session.flush()
        session.query(models.Application).filter_by(id=app_id).update(
            {"resume_version_id": version.id}
        )
        session.commit()
        return app_id, version.id
    finally:
        session.close()


def test_prepare_reports_sensitive_required_fields_and_manual_handoff(client, auth_headers):
    capabilities = client.get("/api/applications/submission-adapters", headers=auth_headers)
    assert capabilities.status_code == 200
    assert {item["kind"] for item in capabilities.json()} == {"manual", "test_destination"}
    assert next(item for item in capabilities.json() if item["kind"] == "test_destination")["live"] is False
    app_id, _ = _application_version(client, auth_headers)
    questions = [
        {"id": "work_authorized", "label": "Authorized?", "required": True},
        {"id": "sponsorship_required", "label": "Need sponsorship?", "required": True},
    ]
    response = client.post(f"/api/applications/{app_id}/prepare", json={"questions": questions}, headers=auth_headers)
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["state"] == "needs_input"
    assert set(data["missing_required"]) == {"work_authorized", "sponsorship_required"}
    assert data["handoff"]["url"] == "https://apply.test/form"
    assert data["adapter"]["kind"] == "manual"
    assert data["answers"] == {}


def test_unknown_destination_never_queues_a_live_submission(client, auth_headers):
    app_id, _ = _application_version(client, auth_headers)
    response = client.post(f"/api/applications/{app_id}/submit", json={
        "questions": [
            {"id": "full_name", "required": True}, {"id": "email", "required": True},
            {"id": "work_authorized", "required": True},
            {"id": "sponsorship_required", "required": True},
        ],
        "answers": {"full_name": "Jane Doe", "email": "jane@example.com",
                    "work_authorized": "yes", "sponsorship_required": "no"},
        "idempotency_key": "manual-1",
    }, headers=auth_headers)
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "manual_handoff"


def test_configured_test_destination_receipt_and_replay_once(client, auth_headers, monkeypatch):
    destination = "https://test-apply.invalid/submit"
    monkeypatch.setenv("SUBMISSION_TEST_URL", destination)
    get_settings.cache_clear()
    app_id, _ = _application_version(client, auth_headers)
    sent = []

    def respond(request):
        sent.append(request)
        data = __import__("json").loads(request.content)
        return httpx.Response(200, json={
            "receipt_id": "receipt-1", "submission_id": data["submission_id"],
        })

    test_destination._transport_override = httpx.MockTransport(respond)
    try:
        payload = {
            "destination_url": destination,
            "answers": {"full_name": "Jane Doe", "email": "jane@example.com",
                        "work_authorized": "yes", "sponsorship_required": "no"},
            "idempotency_key": "test-send-1",
        }
        queued = client.post(f"/api/applications/{app_id}/submit", json=payload, headers=auth_headers)
        assert queued.status_code == 202, queued.text
        task_id = queued.json()["task_id"]
        session = client.app.state.testing_sessionmaker()
        try:
            result = execute(session, task_id)
            assert result["outcome"] == "succeeded", result
            submission = session.query(ApplicationSubmission).one()
            application = session.query(models.Application).filter_by(id=app_id).one()
            assert submission.state == "submitted"
            assert submission.receipt["artifact_sha256"] == submission.artifact_sha256
            assert application.status == "applied"
        finally:
            session.close()
        replay = client.post(f"/api/applications/{app_id}/submit", json=payload, headers=auth_headers)
        assert replay.status_code == 202, replay.text
        assert replay.json()["replayed"] is True
        assert replay.json()["task_id"] == task_id
        assert len(sent) == 1
    finally:
        test_destination._transport_override = None
        get_settings.cache_clear()


def test_same_idempotency_key_rejects_different_package(client, auth_headers, monkeypatch):
    destination = "https://test-apply.invalid/submit"
    monkeypatch.setenv("SUBMISSION_TEST_URL", destination)
    get_settings.cache_clear()
    app_id, _ = _application_version(client, auth_headers)
    payload = {
        "destination_url": destination,
        "answers": {"full_name": "Jane Doe", "email": "jane@example.com",
                    "work_authorized": "yes", "sponsorship_required": "no"},
        "idempotency_key": "conflict-key",
    }
    try:
        first = client.post(f"/api/applications/{app_id}/submit", json=payload, headers=auth_headers)
        assert first.status_code == 202, first.text
        changed = {**payload, "answers": {**payload["answers"], "email": "other@example.com"}}
        second = client.post(f"/api/applications/{app_id}/submit", json=changed, headers=auth_headers)
        assert second.status_code == 409
        assert second.json()["detail"]["code"] == "idempotency_conflict"
    finally:
        get_settings.cache_clear()


def test_ambiguous_timeout_is_unknown_and_never_resubmitted(client, auth_headers, monkeypatch):
    destination = "https://test-apply.invalid/submit"
    monkeypatch.setenv("SUBMISSION_TEST_URL", destination)
    get_settings.cache_clear()
    app_id, _ = _application_version(client, auth_headers)
    calls = []

    def timeout(request):
        calls.append(request)
        raise httpx.ReadTimeout("response lost")

    test_destination._transport_override = httpx.MockTransport(timeout)
    try:
        payload = {
            "destination_url": destination,
            "answers": {"full_name": "Jane Doe", "email": "jane@example.com",
                        "work_authorized": "yes", "sponsorship_required": "no"},
            "idempotency_key": "timeout-key",
        }
        queued = client.post(f"/api/applications/{app_id}/submit", json=payload, headers=auth_headers)
        session = client.app.state.testing_sessionmaker()
        try:
            result = execute(session, queued.json()["task_id"])
            assert result["outcome"] == "failed"
            row = session.query(ApplicationSubmission).one()
            assert row.state == "unknown"
        finally:
            session.close()
        replay = client.post(f"/api/applications/{app_id}/submit", json=payload, headers=auth_headers)
        assert replay.json()["replayed"] is True
        assert len(calls) == 1
        def receipt_lookup(request):
            assert request.method == "GET"
            return httpx.Response(200, json={
                "receipt_id": "late-receipt", "submission_id": request.url.params["submission_id"],
            })
        test_destination._transport_override = httpx.MockTransport(receipt_lookup)
        submission_id = replay.json()["submission_id"]
        reconciled = client.post(
            f"/api/applications/{app_id}/submissions/{submission_id}/reconcile",
            json={"outcome": "check"}, headers=auth_headers,
        )
        assert reconciled.status_code == 200, reconciled.text
        assert reconciled.json()["state"] == "submitted"
        assert reconciled.json()["resolution"] == "submitted"
        session = client.app.state.testing_sessionmaker()
        try:
            assert session.query(models.Application).filter_by(id=app_id).one().status == "applied"
        finally:
            session.close()
    finally:
        test_destination._transport_override = None
        get_settings.cache_clear()


def test_cancelled_queued_submission_does_not_execute(client, auth_headers, monkeypatch):
    destination = "https://test-apply.invalid/submit"
    monkeypatch.setenv("SUBMISSION_TEST_URL", destination)
    get_settings.cache_clear()
    app_id, _ = _application_version(client, auth_headers)
    response = client.post(f"/api/applications/{app_id}/submit", json={
        "destination_url": destination,
        "answers": {"full_name": "Jane Doe", "email": "jane@example.com",
                    "work_authorized": "yes", "sponsorship_required": "no"},
        "idempotency_key": "cancel-key",
    }, headers=auth_headers)
    task_id = response.json()["task_id"]
    submission_id = response.json()["submission_id"]
    cancelled = client.post(
        f"/api/applications/{app_id}/submissions/{submission_id}/cancel", headers=auth_headers
    )
    assert cancelled.status_code == 200
    assert cancelled.json()["state"] == "cancelled"
    session = client.app.state.testing_sessionmaker()
    try:
        task = session.query(TaskRun).filter_by(id=task_id).one()
        assert task.status == "cancelled"
    finally:
        session.close()
    get_settings.cache_clear()


def test_changed_resume_fails_preflight_before_external_effect(client, auth_headers, monkeypatch):
    destination = "https://test-apply.invalid/submit"
    monkeypatch.setenv("SUBMISSION_TEST_URL", destination)
    get_settings.cache_clear()
    app_id, version_id = _application_version(client, auth_headers)
    called = []
    test_destination._transport_override = httpx.MockTransport(
        lambda request: (called.append(request), httpx.Response(200, json={"receipt_id": "unexpected"}))[1]
    )
    try:
        queued = client.post(f"/api/applications/{app_id}/submit", json={
            "destination_url": destination,
            "answers": {"full_name": "Jane Doe", "email": "jane@example.com",
                        "work_authorized": "yes", "sponsorship_required": "no"},
            "idempotency_key": "changed-resume-key",
        }, headers=auth_headers)
        session = client.app.state.testing_sessionmaker()
        try:
            version = session.get(models.ResumeVersion, version_id)
            version.content += "\nUnapproved edit"
            session.commit()
            result = execute(session, queued.json()["task_id"])
            assert result["outcome"] == "failed"
            row = session.query(ApplicationSubmission).one()
            assert row.state == "failed"
            assert "resume text changed" in row.state_reason
            assert called == []
        finally:
            session.close()
    finally:
        test_destination._transport_override = None
        get_settings.cache_clear()
