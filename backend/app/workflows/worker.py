"""Task worker — executes due durable tasks.

Modes (``python -m app.workflows.worker``):
- ``rq`` (requires REDIS_URL): connect to the configured Redis queue and run
  ``executor.perform_task`` via RQ Worker.
- ``poll`` (default without Redis): loop over due ``queued`` tasks in the
  database and execute inline — no queue needed for local development.

Both modes deduplicate deliveries through executor.execute's state guards.
``--once`` processes at most one due task and returns (tests, cron).
"""

import argparse
import sys
import time

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

log = get_logger(__name__)


def due_tasks(db, limit: int = 5) -> list[str]:
    from app.workflows.models import TaskRun

    now = time.time()
    rows = (
        db.query(TaskRun)
        .filter(TaskRun.status == "queued")
        .all()
    )
    due = []
    for task in rows:
        next_at = task.next_attempt_at
        if next_at is None:
            due.append(task.id)
        else:
            from app.workflows.clock import aware, utcnow

            if aware(next_at) <= utcnow():
                due.append(task.id)
    return due[:limit]


def poll_once(limit: int = 5) -> int:
    """Execute up to `limit` due tasks; returns how many were run."""
    from app.db.database import SessionLocal
    from app.workflows import executor

    ran = 0
    db = SessionLocal()
    try:
        ids = due_tasks(db, limit=limit)
    finally:
        db.close()
    for task_id in ids:
        result = executor.perform_task(task_id)
        if result.get("outcome") != "skipped":
            ran += 1
        log.info("task %s -> %s", task_id, result)
    return ran


def run_rq() -> int:
    import redis
    import rq

    settings = get_settings()
    conn = redis.from_url(settings.redis_url)
    worker = rq.Worker(
        [rq.Queue(settings.redis_queue_name, connection=conn)],
        connection=conn,
        name=f"wf-worker-{settings.backend_port or ''}",
    )
    log.info("RQ worker starting on %s (queue=%s)", settings.redis_url, settings.redis_queue_name)
    worker.work(burst=False)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="durable-task worker")
    parser.add_argument("--mode", choices=["auto", "rq", "poll"], default="auto")
    parser.add_argument("--once", action="store_true", help="process at most one batch and exit")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level)
    _assert_db()

    mode = args.mode
    if mode == "auto":
        mode = "rq" if settings.redis_url.strip() else "poll"

    if mode == "rq":
        return run_rq()

    stop = {"flag": False}
    import signal

    signal.signal(signal.SIGINT, lambda *a, **k: stop.update(flag=True))
    signal.signal(signal.SIGTERM, lambda *a, **k: stop.update(flag=True))

    if args.once:
        log.info("poll worker pass: %s tasks ran", poll_once())
        return 0
    log.info("poll worker starting (no Redis configured; DB-driven)")
    while not stop["flag"]:
        poll_once()
        for _ in range(max(int(settings.wf_poll_interval_s * 10), 1)):
            if stop["flag"]:
                break
            time.sleep(0.1)
    log.info("poll worker stopped")
    return 0


def _assert_db() -> None:
    from app.db.database import SessionLocal

    with SessionLocal() as db:
        db.execute(text("SELECT 1"))


if __name__ == "__main__":
    raise SystemExit(main())
