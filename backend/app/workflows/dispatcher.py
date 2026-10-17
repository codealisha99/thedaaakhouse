"""Outbox dispatcher — bridges committed task changes to the queue.

Loop (``python -m app.workflows.dispatcher``):
1. recover expired leases (workers died mid-flight),
2. publish every pending outbox event (queue outage keeps rows pending),
3. sleep ``WF_DISPATCHER_INTERVAL_S``.

Safe to run concurrently with other dispatchers/instances: outbox publication
and lease recovery both use guarded conditional updates.
Run with ``--once`` for a single pass (tests, cron-like schedulers).
"""

import argparse
import signal
import sys

from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging

log = get_logger(__name__)


def run_once() -> dict:
    from app.db.database import SessionLocal
    from app.workflows import executor

    db = SessionLocal()
    try:
        recovered = executor.recover_expired_leases(db)
        published = executor.publish_pending_outbox(db)
        return {"leases_recovered": recovered, "events_published": published}
    finally:
        db.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="durable-task outbox dispatcher")
    parser.add_argument("--once", action="store_true", help="run a single pass and exit")
    args = parser.parse_args()

    settings = get_settings()
    setup_logging(settings.log_level)
    _assert_db()

    stop = {"flag": False}

    def _stop(signum, _frame):  # noqa: ARG001
        stop["flag"] = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    if args.once:
        log.info("dispatcher pass: %s", run_once())
        return 0
    log.info("dispatcher loop starting (interval=%ss, redis=%s)",
             settings.wf_dispatcher_interval_s, bool(settings.redis_url))
    while not stop["flag"]:
        try:
            run_once()
        except Exception:  # keep the loop alive; retry next tick
            log.exception("dispatcher pass failed")
        _sleep(settings.wf_dispatcher_interval_s, stop)
    log.info("dispatcher stopped")
    return 0


def _assert_db() -> None:
    from app.db.database import SessionLocal

    with SessionLocal() as db:
        db.execute(text("SELECT 1"))


def _sleep(seconds: float, stop: dict) -> None:
    for _ in range(max(int(seconds * 10), 1)):
        if stop["flag"]:
            break
        sys.stdout.flush()
        import time

        time.sleep(0.1)


if __name__ == "__main__":
    raise SystemExit(main())
