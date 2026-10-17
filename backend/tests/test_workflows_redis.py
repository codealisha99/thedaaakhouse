"""Durable task engine — real Redis/RQ transport verification (step 02).

Everything in test_workflows_tasks.py and pytest's stub publishers exercises
executor *logic*. This module runs the actual delivery path —
``queue.publish`` → ``rq.Queue`` → ``RQ SimpleWorker`` →
``executor.perform_task`` — against a real Redis, plus the outage case
(QUEUE down ⇒ outbox row stays pending, accepted work is not lost).

Requires ``TEST_REDIS_URL`` (a disposable Redis instance, e.g. the
docker-compose redis):

    docker compose up -d redis
    TEST_REDIS_URL=redis://localhost:6379/15 \
        pytest -q tests/test_workflows_redis.py

Skipped otherwise, so the main suite stays credential-free by design.
"""

import os

import pytest

TEST_REDIS_URL = os.environ.get("TEST_REDIS_URL", "")

pytestmark = pytest.mark.skipif(
    not TEST_REDIS_URL,
    reason="requires TEST_REDIS_URL (a disposable Redis instance)",
)


@pytest.fixture()
def engine(tmp_path, monkeypatch):
    """Task-state database (SQLite) + patched SessionLocal so the RQ job's
    perform_task call lands on the test database."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.orm import sessionmaker

    import app.db.database as dbm
    import app.db.models  # noqa: F401 — register tables
    import app.discovery.models  # noqa: F401
    import app.workflows.models  # noqa: F401
    from app.db.database import Base

    eng = create_engine(
        f"sqlite:///{tmp_path/'rq.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(eng)
    Testing = sessionmaker(bind=eng, autoflush=False, autocommit=False)

    with eng.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE rq_probe_runs (
                    id integer PRIMARY KEY AUTOINCREMENT,
                    task_id varchar(36) NOT NULL
                )
                """
            )
        )

    # perform_task imports SessionLocal from the module at call time
    monkeypatch.setattr(dbm, "SessionLocal", Testing)
    # warn via settings: point the app at the same DB and the real test Redis
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path/'rq.db'}")
    monkeypatch.setenv("REDIS_URL", TEST_REDIS_URL)
    monkeypatch.setenv("REDIS_QUEUE_NAME", "tasks-pg-test")
    from app.core.config import get_settings

    get_settings.cache_clear()
    yield {"engine": eng, "sessionmaker": Testing}
    get_settings.cache_clear()
    eng.dispose()


@pytest.fixture()
def user_id(engine):
    from app.db import models

    db = engine["sessionmaker"]()
    try:
        u = models.User(username="rquser", password_hash="x")
        db.add(u)
        db.commit()
        return u.id
    finally:
        db.close()


def _enqueue(user_id, payload=None, **kw):
    from app.workflows.service import TaskService

    db = _ENGINE["sessionmaker"]()
    try:
        task, replayed = TaskService(db, user_id).enqueue(
            "tests_rq.probe", payload or {"marker": "m"}, **kw
        )
        return task.id, replayed
    finally:
        db.close()


def _probe(payload, ctx):
    from sqlalchemy import text

    ctx.db.execute(
        text("INSERT INTO rq_probe_runs (task_id) VALUES (:t)"), {"t": ctx.task.id}
    )
    ctx.db.commit()
    return {"ran": True}


from app.workflows import handlers as _handlers  # noqa: E402

_handlers.register("tests_rq.probe", external_side_effect=False, summary="rq probe")(_probe)

_ENGINE = None


@pytest.fixture(autouse=True)
def _bind_engine(engine):
    global _ENGINE
    _ENGINE = engine
    yield
    _ENGINE = None


def _probe_count():
    from sqlalchemy import text

    db = _ENGINE["sessionmaker"]()
    try:
        return db.execute(text("SELECT count(*) FROM rq_probe_runs")).scalar()
    finally:
        db.close()


def _task(task_id):
    from app.workflows.models import TaskRun

    db = _ENGINE["sessionmaker"]()
    try:
        return db.query(TaskRun).filter_by(id=task_id).one()
    finally:
        db.close()


def _run_burst_worker():
    """Run one in-process RQ worker pass (same code path as `rq` mode)."""
    import redis
    import rq
    from app.core.config import get_settings

    settings = get_settings()
    conn = redis.from_url(settings.redis_url)
    worker = rq.SimpleWorker(
        [rq.Queue(settings.redis_queue_name, connection=conn)],
        connection=conn,
    )
    worker.work(burst=True)


def test_real_queue_delivery_runs_task_once(user_id):
    from app.workflows.executor import publish_pending_outbox
    from app.workflows.models import OutboxEvent
    from app.workflows.queue import publish as queue_publish

    task_id, _ = _enqueue(user_id)
    assert _task(task_id).status == "queued"

    db = _ENGINE["sessionmaker"]()
    try:
        published = publish_pending_outbox(db, publisher=queue_publish)
        assert published == 1
    finally:
        db.close()

    _run_burst_worker()

    row = _task(task_id)
    assert row.status == "succeeded", row
    assert _probe_count() == 1
    db = _ENGINE["sessionmaker"]()
    try:
        assert db.query(OutboxEvent).filter_by(task_id=task_id).one().status == "published"
    finally:
        db.close()


def test_duplicate_queue_delivery_never_reruns(user_id):
    """A second RQ job for the same task (queue redelivery/outbox replay)
    must not re-execute completed work (real transport end to end)."""
    from app.workflows.executor import publish_pending_outbox, perform_task
    from app.workflows.queue import publish as queue_publish

    task_id, _ = _enqueue(user_id)
    db = _ENGINE["sessionmaker"]()
    try:
        assert publish_pending_outbox(db, publisher=queue_publish) == 1
    finally:
        db.close()
    _run_burst_worker()
    assert _task(task_id).status == "succeeded"
    assert _probe_count() == 1

    # simulate a duplicate delivery: enqueue the same task again through the
    # real transport and drain it
    import redis
    import rq
    from app.core.config import get_settings

    settings = get_settings()
    conn = redis.from_url(settings.redis_url)
    rq.Queue(settings.redis_queue_name, connection=conn).enqueue(
        perform_task, task_id=task_id
    )
    _run_burst_worker()

    row = _task(task_id)
    assert row.status == "succeeded" and row.attempts == 1
    assert _probe_count() == 1


def test_redis_outage_leaves_outbox_pending(user_id):
    """Publishing against a dead Redis must leave the outbox row pending —
    accepted work cannot be lost by a queue outage."""
    import os

    from app.workflows.executor import publish_pending_outbox
    from app.workflows.models import OutboxEvent
    from app.workflows.queue import publish as queue_publish

    task_id, _ = _enqueue(user_id)

    # uncache settings so the dead URL is honored, then publish
    from app.core import config as config_module
    from app.core.config import get_settings

    original_env = os.environ.get("REDIS_URL")
    os.environ["REDIS_URL"] = "redis://localhost:6399/0"  # nothing listens here
    get_settings.cache_clear()
    try:
        db = _ENGINE["sessionmaker"]()
        try:
            published = publish_pending_outbox(db, publisher=queue_publish)
            assert published == 0  # queue refused; row stays pending
        finally:
            db.close()
    finally:
        if original_env is None:
            os.environ.pop("REDIS_URL", None)
        else:
            os.environ["REDIS_URL"] = original_env
        get_settings.cache_clear()

    db = _ENGINE["sessionmaker"]()
    try:
        row = db.query(OutboxEvent).filter_by(task_id=task_id).one()
        assert row.status == "pending"
    finally:
        db.close()

    # the healthy dispatcher recovers: publish + one worker pass later
    db = _ENGINE["sessionmaker"]()
    try:
        assert publish_pending_outbox(db, publisher=queue_publish) == 1
    finally:
        db.close()
    _run_burst_worker()
    assert _task(task_id).status == "succeeded"
    assert _probe_count() == 1
