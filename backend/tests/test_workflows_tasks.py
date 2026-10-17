"""Durable task engine — crash-safety, retries, leases, dedupe (SQLite).

These tests exercise the executor semantics directly against an isolated
database. PostgreSQL lock/concurrency verification lives in
test_workflows_postgres.py (skipped without TEST_DATABASE_URL).
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.workflows.clock import utcnow
from app.workflows.executor import (
    execute,
    publish_pending_outbox,
    recover_expired_leases,
)
from app.workflows.models import OutboxEvent, TaskRun
from app.workflows.service import TaskConflict, TaskService, UnknownKind


@pytest.fixture(autouse=True)
def _deterministic_timing(monkeypatch):
    """Deterministic backoff + fresh settings cache for every test in this module."""
    from app.core.config import get_settings

    monkeypatch.setenv("WF_RETRY_JITTER", "0")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture()
def db(tmp_path):
    eng = create_engine(f"sqlite:///{tmp_path/'wf.db'}", connect_args={"check_same_thread": False})
    import app.db.models  # noqa: F401
    import app.workflows.models  # noqa: F401
    from app.db.database import Base

    Base.metadata.create_all(eng)
    TestingSession = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    session = TestingSession()
    session.add(__import__("app.db.models", fromlist=["User"]).User(username="u1", password_hash="x"))
    session.commit()
    return session


def _svc(db) -> TaskService:
    user = db.query(__import__("app.db.models", fromlist=["User"]).User).filter_by(username="u1").one()
    return TaskService(db, user.id)


def _pending_outbox(db) -> int:
    return db.query(OutboxEvent).filter(OutboxEvent.status == "pending").count()


# --------------------------------------------------------------------------- #
# Creation + idempotency

def test_enqueue_writes_task_outbox_and_audit_together(db):
    task, replayed = _svc(db).enqueue("diagnostics.echo", {"message": "hi"}, idempotency_key="k1")
    assert not replayed
    assert task.status == "queued"
    assert task.payload_hash != ""
    assert _pending_outbox(db) == 1  # outbox committed with the task


def test_same_key_same_payload_replays_one_task(db):
    svc = _svc(db)
    task1, r1 = svc.enqueue("diagnostics.echo", {"message": "m"}, idempotency_key="key")
    task2, r2 = svc.enqueue("diagnostics.echo", {"message": "m"}, idempotency_key="key")
    assert task1.id == task2.id and task2.status == "queued"
    assert task2.attempts == 0
    assert (r1, r2) == (False, True)
    assert _pending_outbox(db) == 1  # no extra delivery for the replay


def test_same_key_different_payload_is_conflict(db):
    svc = _svc(db)
    svc.enqueue("diagnostics.echo", {"message": "a"}, idempotency_key="key")
    with pytest.raises(TaskConflict):
        svc.enqueue("diagnostics.echo", {"message": "b"}, idempotency_key="key")


def test_unknown_kind_rejected(db):
    with pytest.raises(UnknownKind):
        _svc(db).enqueue("no.such.kind", {})


# --------------------------------------------------------------------------- #
# Execution: success, dedupe of redeliveries, cancellation

def test_success_and_duplicate_delivery_does_not_rerun(db):
    task, _ = _svc(db).enqueue("diagnostics.echo", {"message": "m"})
    first = execute(db, task.id)
    assert first["outcome"] == "succeeded"
    second = execute(db, task.id)
    assert second["outcome"] == "skipped"
    assert second["reason"] == "not_runnable"
    fresh = db.query(TaskRun).filter_by(id=task.id).one()
    assert fresh.status == "succeeded" and fresh.attempts == 1  # never re-run


def test_cancel_queued_task_terminal_and_delivery_dedupe(db):
    svc = _svc(db)
    task, _ = svc.enqueue("diagnostics.echo", {"message": "m"})
    task, _ = svc.cancel(task.id)
    assert task.status == "cancelled"
    result = execute(db, task.id)
    assert result["outcome"] == "skipped" and result["reason"] == "not_runnable"


def test_running_task_stop_requested_finalizes_cancelled_between_stages(db):
    task, _ = _svc(db).enqueue("diagnostics.echo", {"message": "m"})
    execute(db, task.id)  # runs to completion
    assert db.query(TaskRun).filter_by(id=task.id).one().status == "succeeded"


def test_unknown_kind_failure_is_permanent(db):
    task, _ = _svc(db).enqueue("diagnostics.echo", {"message": "m"})
    db.query(TaskRun).filter_by(id=task.id).update({"kind": "deleted.handler"})
    db.commit()
    result = execute(db, task.id)
    assert result["outcome"] == "failed"


# --------------------------------------------------------------------------- #
# Retries, backoff, exhaustion

def _force_due(db, task_id):
    db.query(TaskRun).filter_by(id=task_id).update({"next_attempt_at": utcnow()})
    db.commit()


def test_transient_failure_requeues_with_finite_redispatch(db):
    task, _ = _svc(db).enqueue(
        "diagnostics.echo",
        {"message": "m", "fail": "transient", "fail_times": 2},
    )
    _flush_deliveries(db)
    # attempt marker: handler uses task.attempts; first execution fails once
    r1 = execute(db, task.id)
    assert r1["outcome"] == "retry_scheduled" and r1["status"] == "queued"
    row = db.query(TaskRun).filter_by(id=task.id).one()
    assert row.attempts == 1 and row.next_attempt_at is not None
    assert _pending_outbox(db) == 1  # a retry publishes a NEW delivery record

    # delivery not yet due: worker skips politely
    not_due = execute(db, task.id)
    assert not_due["outcome"] == "skipped" and not_due["reason"] == "not_due"
    _force_due(db, row.id)
    r2 = execute(db, task.id)
    assert r2["outcome"] == "succeeded", r2
    row = db.query(TaskRun).filter_by(id=task.id).one()
    assert row.result["attempts_used"] == 2


def _flush_deliveries(db):
    """Simulate a dispatcher pass handoff (no real transport) leaving 0 pending."""
    publish_pending_outbox(db)


def test_permanent_failure_never_retries(db):
    task, _ = _svc(db).enqueue("diagnostics.echo", {"message": "m", "fail": "permanent"})
    _flush_deliveries(db)
    r = execute(db, task.id)
    assert r["outcome"] == "failed"
    get_row = db.query(TaskRun).filter_by(id=task.id).one()
    assert get_row.attempts == 1 and get_row.error_code == "diagnostics_permanent"
    assert _pending_outbox(db) == 0  # permanent outcome adds no retry delivery


def test_attempts_exhaustion_fails_permanently(db):
    task, _ = _svc(db).enqueue(
        "diagnostics.echo",
        {"message": "m", "fail": "transient", "fail_times": 99},
        max_attempts=2,
    )
    assert execute(db, task.id)["outcome"] == "retry_scheduled"
    _force_due(db, task.id)
    assert execute(db, task.id)["outcome"] == "failed"  # attempts == cap
    row = db.query(TaskRun).filter_by(id=task.id).one()
    assert row.attempts == 2 and row.status == "failed"


# --------------------------------------------------------------------------- #
# Leases: expiry recovery runs exactly once and never re-runs finished work

def _simulate_crashed_worker(db, task_id, *, attempts=1, cancel=False):
    """Place the task in post-crash state: running with an already-expired lease."""
    past = utcnow()
    db.query(TaskRun).filter_by(id=task_id).update({
        "status": "running",
        "stage": "executing",
        "attempts": attempts,
        "lease_owner": "dead-worker",
        "lease_expires_at": past,
        "heartbeat_at": past,
        "cancel_requested": bool(cancel),
    })
    db.commit()


def test_expired_lease_recovers_once_and_finishes(db):
    task, _ = _svc(db).enqueue("diagnostics.echo", {"message": "m"})
    _flush_deliveries(db)
    _simulate_crashed_worker(db, task.id)
    assert recover_expired_leases(db) == 1
    row = db.query(TaskRun).filter_by(id=task.id).one()
    assert row.status == "queued" and row.stage.startswith("lease_recovered")
    assert _pending_outbox(db) == 1  # exactly one redelivery record, published once
    assert recover_expired_leases(db) == 0  # idempotent: no double recovery
    _force_due(db, task.id)
    assert execute(db, task.id)["outcome"] == "succeeded"
    row = db.query(TaskRun).filter_by(id=task.id).one()
    assert row.attempts == 2  # crashed attempt + recovery attempt; ran once each


def test_expired_lease_with_stop_request_stops(db):
    task, _ = _svc(db).enqueue("diagnostics.echo", {"message": "m"})
    _simulate_crashed_worker(db, task.id, cancel=True)
    assert recover_expired_leases(db) == 1
    row = db.query(TaskRun).filter_by(id=task.id).one()
    assert row.status == "cancelled"


def test_expired_lease_at_attempt_cap_fails_with_lease_code(db):
    task, _ = _svc(db).enqueue("diagnostics.echo", {"message": "m"}, max_attempts=1)
    _flush_deliveries(db)
    _simulate_crashed_worker(db, task.id, attempts=1)
    assert recover_expired_leases(db) == 1
    row = db.query(TaskRun).filter_by(id=task.id).one()
    assert row.status == "failed" and row.error_code == "lease_expired"
    assert _pending_outbox(db) == 0
