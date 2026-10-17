"""Durable task engine — PostgreSQL lock/concurrency verification (step 02).

SQLite unit tests (test_workflows_tasks.py, test_workflows_automation.py)
prove the executor *logic*. This module proves the concurrency guarantees
against a real PostgreSQL database, where ``SELECT ... FOR UPDATE`` and the
unique idempotency constraint actually engage:

1. concurrent identical requests create one logical task,
2. a crash after DB commit recovers publication (transactional outbox),
3. duplicate queue deliveries never repeat completed work,
4. two concurrent workers cannot both claim one task,
5. two recovering dispatchers recover one expired lease exactly once,
6. revoked standing policy is respected on a PostgreSQL retry.

Requires ``TEST_DATABASE_URL`` pointing at an empty, disposable database:

    docker compose up -d db
    createdb -h localhost -U thedaaakhouse thedaaakhouse_tasks_test
    pytest -q tests/test_workflows_postgres.py

Skipped otherwise, so the main suite stays credential-free by design.
"""

import os
import threading

import pytest

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL.startswith("postgresql"),
    reason="requires TEST_DATABASE_URL (a disposable PostgreSQL database)",
)

handlers = pytest.importorskip("app.workflows.handlers")
from app.workflows.handlers import TaskFailure  # noqa: E402

# --------------------------------------------------------------------------- #
# Fixtures: real Postgres, fresh schema per test, DB-authoritative run counter
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def migrated_sqlalchemy_url():
    """Run the checked-in Alembic graph against the disposable PG database.

    This doubles as PostgreSQL migration verification: the baseline used to
    fail here because CREATE TABLE referenced not-yet-existing tables
    (SQLite never enforced FK existence at creation).
    """
    from alembic import command
    from alembic.config import Config

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cfg = Config(os.path.join(root, "backend", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(root, "backend", "alembic"))
    cfg.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.upgrade(cfg, "head")
    return TEST_DATABASE_URL


@pytest.fixture()
def pg(migrated_sqlalchemy_url):
    from sqlalchemy import create_engine, inspect, text
    from sqlalchemy.orm import sessionmaker

    eng = create_engine(TEST_DATABASE_URL, pool_size=12, max_overflow=0, pool_pre_ping=True)

    # Truncate every data table, but keep `alembic_version` intact: the
    # migration stamp is part of the schema state, not of the test data.
    insp = inspect(eng)
    names = [t for t in insp.get_table_names(schema="public") if t != "alembic_version"]
    tables = ", ".join(f'"{t}"' for t in names)
    if tables:
        with eng.begin() as conn:
            conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))

    with eng.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS pg_probe_runs (
                    id bigserial PRIMARY KEY,
                    task_id varchar(36) NOT NULL,
                    created_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
        )

    Testing = sessionmaker(bind=eng, autoflush=False, autocommit=False)
    yield {"engine": eng, "sessionmaker": Testing}
    eng.dispose()


@pytest.fixture()
def user_id(pg):
    from app.db import models

    db = pg["sessionmaker"]()
    try:
        u = models.User(username="pguser", password_hash="x")
        db.add(u)
        db.commit()
        return u.id
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# Probe handler: records executions in the probe table so counts are
# DB-authoritative across threads (no in-memory state).
# --------------------------------------------------------------------------- #

_probe_lock = threading.Lock()
_probe_fail_n = {"n": 0}

PROBE_KIND = "tests_pg.probe"
PROBE_EXTERNAL = "tests_pg.external_probe"


def _probe(payload, ctx):
    from sqlalchemy import text

    fail_times = int(payload.get("fail_times", 0) or 0)
    if fail_times:
        with _probe_lock:
            if _probe_fail_n["n"] < fail_times:
                _probe_fail_n["n"] += 1
                raise TaskFailure("tests_pg_probe_transient", "injected probe transient failure")
    ctx.db.execute(
        text("INSERT INTO pg_probe_runs (task_id) VALUES (:t)"), {"t": ctx.task.id}
    )
    ctx.db.commit()
    return {"ran": True}


handlers.register(PROBE_KIND, external_side_effect=False, summary="pg probe")(_probe)
handlers.register(PROBE_EXTERNAL, external_side_effect=True, summary="pg external probe")(_probe)


# --------------------------------------------------------------------------- #
# Helpers


def _enqueue(uid, kind=PROBE_KIND, payload=None, **kw):
    from app.workflows.service import TaskService

    db = pg_sessionmaker()()
    try:
        task, replayed = TaskService(db, uid).enqueue(kind, payload or {"marker": "m"}, **kw)
        return task.id, replayed
    finally:
        db.close()


def pg_sessionmaker():
    return _PG["sessionmaker"]


_PG = None  # bound per-test by the pg fixture


@pytest.fixture(autouse=True)
def _bind_pg(pg):
    global _PG
    _PG = pg
    yield
    from app.workflows import handlers as _h

    _PG = None
    _probe_fail_n["n"] = 0


def _run_threads(fn, n, timeout=60):
    results = [None] * n

    def worker(i):
        try:
            results[i] = ("ok", fn(i))
        except Exception as exc:  # surface the exception class, not the traceback
            results[i] = ("error", f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout)
        if t.is_alive():
            raise AssertionError("thread hung")
    return results


def _probe_run_count():
    from sqlalchemy import text

    db = pg_sessionmaker()()
    try:
        return db.execute(text("SELECT count(*) FROM pg_probe_runs")).scalar()
    finally:
        db.close()


def _task(task_id):
    from app.workflows.models import TaskRun

    db = pg_sessionmaker()()
    try:
        return db.query(TaskRun).filter_by(id=task_id).one()
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# 1. Concurrent identical requests create one logical task


def test_concurrent_enqueue_same_key_same_payload_one_task(user_id):
    ids = []
    replays = []

    def enq(_i):
        task_id, replayed = _enqueue(user_id, payload={"marker": "same"}, idempotency_key=".team")
        ids.append(task_id)
        replays.append(replayed)

    _run_threads(enq, 8)
    assert len(set(ids)) == 1, f"expected one logical task, got {set(ids)}"
    assert replays.count(False) == 1, f"exactly one request created the task: {replays}"
    assert replays.count(True) == 7

    from app.workflows.models import OutboxEvent

    db = pg_sessionmaker()()
    try:
        assert db.query(OutboxEvent).filter_by(task_id=ids[0]).count() == 1
    finally:
        db.close()


def test_concurrent_enqueue_same_key_different_payload_conflicts(user_id):
    _enqueue(user_id, payload={"marker": "original"}, idempotency_key="pk1")

    from app.workflows.service import TaskConflict

    def enq(i):
        _enqueue(user_id, payload={"marker": f"variant-{i}"}, idempotency_key="pk1")
        return None

    results = _run_threads(enq, 4)
    conflicts = [r for s, r in results if s == "error" and r.startswith("TaskConflict")]
    assert len(conflicts) == 4, (results, conflicts)
    assert _probe_run_count() == 0


# --------------------------------------------------------------------------- #
# 2. Crash after DB commit recovers publication (transactional outbox)


def test_crash_after_commit_recovers_publication(user_id):
    task_id, _ = _enqueue(user_id)
    from app.workflows.executor import execute, publish_pending_outbox
    from app.workflows.models import OutboxEvent

    def dead_queue(_tid):
        raise ConnectionError("queue down")

    db = pg_sessionmaker()()
    try:
        assert publish_pending_outbox(db, publisher=dead_queue) == 0
        assert db.query(OutboxEvent).filter_by(task_id=task_id, status="pending").count() == 1
    finally:
        db.close()

    db = pg_sessionmaker()()
    try:
        assert publish_pending_outbox(db, publisher=lambda tid: True) == 1
    finally:
        db.close()

    db = pg_sessionmaker()()
    try:
        result = execute(db, task_id)
    finally:
        db.close()
    assert result["outcome"] == "succeeded"
    assert _probe_run_count() == 1

    db = pg_sessionmaker()()
    try:
        assert db.query(OutboxEvent).filter_by(task_id=task_id, status="published").count() == 1
        assert db.query(OutboxEvent).filter_by(task_id=task_id, status="pending").count() == 0
    finally:
        db.close()


# --------------------------------------------------------------------------- #
# 3 + 4. Duplicate deliveries / concurrent workers: handler runs exactly once


def test_concurrent_workers_single_claim(user_id):
    task_id, _ = _enqueue(user_id)
    from app.workflows.executor import execute

    outcomes = []

    def run(i):
        db = pg_sessionmaker()()
        try:
            res = execute(db, task_id, worker_id=f"w{i}")
            outcomes.append((res["outcome"], res.get("reason")))
        finally:
            db.close()

    _run_threads(run, 6)
    assert _probe_run_count() == 1, "handler must run exactly once under concurrent claim"
    succeeded = [o for o, _ in outcomes if o == "succeeded"]
    skipped = [o for o, _ in outcomes if o == "skipped"]
    assert len(succeeded) == 1 and len(skipped) == 5, outcomes
    row = _task(task_id)
    assert row.status == "succeeded" and row.attempts == 1


def test_redelivery_after_completion_never_reruns(user_id):
    task_id, _ = _enqueue(user_id)
    from app.workflows.executor import execute

    db = pg_sessionmaker()()
    try:
        assert execute(db, task_id)["outcome"] == "succeeded"
    finally:
        db.close()

    out = []
    for _ in range(3):
        db = pg_sessionmaker()()
        try:
            out.append(execute(db, task_id, worker_id="late-redelivery"))
        finally:
            db.close()
    assert all(o["outcome"] == "skipped" and o["reason"] == "not_runnable" for o in out)
    assert _probe_run_count() == 1


# --------------------------------------------------------------------------- #
# 5. Two recovering dispatchers recover one expired lease exactly once


def test_expired_lease_recovered_once_concurrently(user_id):
    task_id, _ = _enqueue(user_id)
    from app.workflows.clock import utcnow
    from app.workflows.executor import execute, publish_pending_outbox, recover_expired_leases
    from app.workflows.models import TaskRun

    # deliver the initial event as a healthy dispatcher would, so only the
    # (single) recovery redelivery is pending afterwards
    db = pg_sessionmaker()()
    try:
        assert publish_pending_outbox(db, publisher=lambda tid: True) == 1
    finally:
        db.close()

    db = pg_sessionmaker()()
    try:
        db.query(TaskRun).filter_by(id=task_id).update(
            {
                "status": "running",
                "stage": "executing",
                "attempts": 1,
                "lease_owner": "dead-worker",
                "lease_expires_at": utcnow(),
                "heartbeat_at": utcnow(),
            }
        )
        db.commit()
    finally:
        db.close()

    recovered_total = [0]

    def recover(_i):
        db = pg_sessionmaker()()
        try:
            recovered_total[0] += recover_expired_leases(db)
        finally:
            db.close()

    _run_threads(recover, 4)
    assert recovered_total[0] == 1

    from app.workflows.models import OutboxEvent

    db = pg_sessionmaker()()
    try:
        pending = db.query(OutboxEvent).filter_by(task_id=task_id, status="pending").count()
        assert pending == 1, "exactly one redelivery record for the recovered lease"
        row = db.query(TaskRun).filter_by(id=task_id).one()
        assert row.status == "queued" and row.stage.startswith("lease_recovered")
    finally:
        db.close()

    db = pg_sessionmaker()()
    try:
        result = execute(db, task_id)  # recovery attempt counts toward max_attempts
    finally:
        db.close()
    assert result["outcome"] == "succeeded", result
    assert _probe_run_count() == 1
    assert _task(task_id).attempts == 2


# --------------------------------------------------------------------------- #
# 6. Revoked standing policy is respected on a PostgreSQL retry


def test_revoked_policy_blocks_pg_retry(user_id):
    task_id, _ = _enqueue(
        user_id, kind=PROBE_EXTERNAL, payload={"marker": "m", "fail_times": 4}, max_attempts=5
    )
    from app.db import models
    from app.workflows.automation import AutomationService
    from app.workflows.clock import utcnow
    from app.workflows.executor import execute
    from app.workflows.models import AutomationPolicy, TaskRun

    db = pg_sessionmaker()()
    try:
        AutomationService(db, user_id).create_policy(
            name="pg-policy", allowed_actions=[PROBE_EXTERNAL], constraints={"daily_limit": 10}
        )
        assert db.query(models.User).filter_by(id=user_id).one() is not None
    finally:
        db.close()

    db = pg_sessionmaker()()
    try:
        first = execute(db, task_id, worker_id="w1")  # granted via active policy
    finally:
        db.close()
    assert first["outcome"] == "retry_scheduled", first

    db = pg_sessionmaker()()
    try:
        db.query(AutomationPolicy).update({"status": "revoked", "revoked_at": utcnow()})
        db.commit()
        db.query(TaskRun).filter_by(id=task_id).update({"next_attempt_at": utcnow()})
        db.commit()
    finally:
        db.close()

    db = pg_sessionmaker()()
    try:
        second = execute(db, task_id, worker_id="w2")
    finally:
        db.close()
    assert second["outcome"] == "failed", second
    assert _task(task_id).error_code == "authorization_revoked"
    assert _probe_run_count() == 0


def test_cancelled_queued_task_never_runs_under_concurrent_execute(user_id):
    task_id, _ = _enqueue(user_id)
    from app.workflows.executor import execute
    from app.workflows.service import TaskService

    db = pg_sessionmaker()()
    try:
        TaskService(db, user_id).cancel(task_id)
    finally:
        db.close()

    res = {}

    def run(i):
        db = pg_sessionmaker()()
        try:
            res[i] = execute(db, task_id, worker_id=f"w{i}")
        finally:
            db.close()

    _run_threads(run, 4)
    assert all(o["outcome"] == "skipped" and o["reason"] == "not_runnable" for o in res.values()), res
    assert _task(task_id).status == "cancelled"
    assert _probe_run_count() == 0
