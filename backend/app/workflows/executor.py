"""Executor — worker-side task execution on top of authoritative DB state.

Claim semantics (one worker owns a task at a time):

1. A redelivered task whose status is not ``queued`` is skipped, so duplicate
   queue deliveries can never repeat completed work.
2. Claiming is a conditional UPDATE ``SET status='running' ... WHERE
   status='queued'`` committed before any handler runs; the row count decides
   the winner, so two concurrent workers (PostgreSQL) cannot both run a task.
3. The lease carries ``lease_owner`` + ``lease_expires_at``; handlers extend
   it via ``ctx.heartbeat()``. ``recover_expired_leases`` requeues (or fails
   at max attempts) exactly one task per expired lease, atomically.
4. Cancellation is honored before claiming, before authorization, and by
   handlers via ``ctx.cancelled()``. A completed handler result is kept even
   if a cancellation raced in: accepted external effects are never undone.
5. Transient failures requeue with finite jittered-exponential backoff and a
   NEW pending outbox event written in the same transaction as the state
   change; permanent failures (invalid input, authorization denial, attempts
   exhausted, expired lease at cap) fail immediately.
"""

import math
import random
from datetime import timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.workflows import queue
from app.workflows import handlers
from app.workflows.clock import aware, utcnow
from app.workflows.models import ActionApproval, OutboxEvent, TaskRun
from app.workflows.service import audit
# Register external side-effect handlers in every worker process, not just
# the API process that imports application routes.
import app.submissions.service  # noqa: F401
import app.outreach.gmail  # noqa: F401

log = get_logger(__name__)

#: A stuck `delivering` outbox row older than this is pending again.
OUTBOX_INFLIGHT_STALE_S = 300


def perform_task(task_id: str) -> dict:
    """Queue entry point (RQ job): fresh session per delivery."""
    from app.db.database import SessionLocal

    session = SessionLocal()
    try:
        return execute(session, task_id)
    finally:
        session.close()


def execute(db: Session, task_id: str, worker_id: str = "inline") -> dict:
    """Run one delivery of one task. Safe to call more than once per task."""
    task = _lock(db, task_id)
    if task is None:
        return skip("missing")
    if task.status != "queued":
        return skip("not_runnable", task)  # covers succeeded/failed/cancelled redeliveries
    if task.cancel_requested:
        return _finalize_cancelled(db, task)
    if task.next_attempt_at is not None and aware(task.next_attempt_at) > utcnow():
        return skip("not_due", task)

    if not _claim(db, task, worker_id):
        return skip("claimed_elsewhere", task)
    task = _lock(db, task_id)
    task.stage = "claimed"
    db.commit()

    if task.cancel_requested:
        return _finalize_cancelled(db, task)

    spec = handlers.get_handler(task.kind)
    if spec is None:
        return _finalize_failed(db, task, "unknown_kind", f"no handler for kind {task.kind!r}", permanent=True)

    if spec.external_side_effect:
        try:
            from app.workflows import authorization

            authorization.authorize_action(db, task.user_id, task.kind, task.payload_hash, task)
        except authorization.AuthorizationDenied as exc:
            return _finalize_failed(db, task, exc.code, exc.detail, permanent=True, actor="worker")
        if task.cancel_requested:
            return _finalize_cancelled(db, task)

    task.stage = "executing"
    db.commit()
    ctx = handlers.TaskContext(db, task, worker_id=worker_id)
    try:
        result = handlers.run_task(task.kind, dict(task.payload or {}), ctx)
    except handlers.TaskPermanentFailure as exc:
        return _finalize_failed(db, task, exc.code, exc.detail, permanent=True)
    except handlers.TaskFailure as exc:
        if task.cancel_requested:
            return _finalize_cancelled(db, task)
        return _finalize_retry(db, task, exc.code, exc.detail)
    except Exception as exc:  # unknown bug class: bounded retry, then give up
        if task.cancel_requested:
            return _finalize_cancelled(db, task)
        return _finalize_retry(db, task, "task_failed", f"{type(exc).__name__}: {exc}")
    return _finalize_success(db, task, result)


# --------------------------------------------------------------------------- #
# Claim / lease

def _lock(db: Session, task_id: str) -> TaskRun | None:
    q = db.query(TaskRun).filter_by(id=task_id)
    if db.bind.dialect.name != "sqlite":
        q = q.with_for_update()
    return q.first()


def _claim(db: Session, task: TaskRun, worker_id: str) -> bool:
    now = utcnow()
    settings = get_settings()
    res = db.execute(
        update(TaskRun)
        .where(TaskRun.id == task.id, TaskRun.status == "queued")
        .values(
            status="running",
            lease_owner=worker_id,
            lease_expires_at=now + timedelta(seconds=settings.wf_lease_seconds),
            heartbeat_at=now,
            attempts=TaskRun.attempts + 1,
        )
    )
    db.commit()
    return bool(res.rowcount)


def recover_expired_leases(db: Session) -> int:
    """Requeue (or fail at cap) tasks whose worker died mid-flight. Called
    after restarts and periodically by the dispatcher; the atomic re-queue
    update ensures two recovering dispatchers cannot both claim one task."""
    now = utcnow()
    recovered = 0
    for task in db.query(TaskRun).filter(TaskRun.status == "running").all():
        if task.lease_expires_at is None or aware(task.lease_expires_at) > now:
            continue
        res = db.execute(
            update(TaskRun)
            .where(TaskRun.id == task.id, TaskRun.status == "running")
            .values(status="recovered", heartbeat_at=now)
        )
        db.commit()
        if not res.rowcount:
            continue
        recovered += 1
        task = _lock(db, task.id)
        if task.cancel_requested:
            _finalize_cancelled(db, task)
        elif task.attempts >= task.max_attempts:
            _finalize_failed(db, task, "lease_expired",
                             "worker died before completing the task", permanent=True, actor="system")
        else:
            task.status = "queued"
            task.stage = f"lease_recovered_attempt_{task.attempts}"
            task.lease_owner = None
            task.lease_expires_at = None
            task.next_attempt_at = now
            db.add(OutboxEvent(task_id=task.id, event_type="deliver"))
            audit(db, "task.lease_recovered", task.user_id, object_id=task.id,
                  actor="system", detail={"attempts": task.attempts})
            db.commit()
    return recovered


# --------------------------------------------------------------------------- #
# Outbox publication (shared with dispatcher)

def publish_pending_outbox(db: Session, publisher=None) -> int:
    """Publish every pending outbox event. Publication failure leaves rows
    pending (retried next tick) — a queue outage can never lose accepted work.
    Duplicate publications are safe: workers deduplicate by task state."""
    publisher = publisher or queue.publish
    published = 0
    _requeue_stale_delivering(db)
    for event in _pending_events(db):
        if _transition_outbox(db, event, "delivering"):
            try:
                took = publisher(event.task_id)
            except Exception as exc:  # queue down: leave pending for retry
                _transition_outbox(db, event, "pending", error=f"{type(exc).__name__}: {exc}")
                log.warning("outbox publish attempt failed, event stays pending")
                continue
            if took:
                _transition_outbox(db, event, "published")
                published += 1
    return published


def _pending_events(db: Session) -> list[OutboxEvent]:
    return (
        db.query(OutboxEvent)
        .filter(OutboxEvent.status == "pending")
        .order_by(OutboxEvent.created_at.asc(), OutboxEvent.id.asc())
        .limit(200)
        .all()
    )


def _requeue_stale_delivering(db: Session) -> None:
    stale_before = utcnow() - timedelta(seconds=OUTBOX_INFLIGHT_STALE_S)
    db.execute(
        update(OutboxEvent)
        .where(OutboxEvent.status == "delivering", OutboxEvent.updated_at < stale_before)
        .values(status="pending")
    )
    db.commit()


def _transition_outbox(db: Session, event: OutboxEvent, to_status: str, error: str | None = None) -> bool:
    """State-machine UPDATE with from-status guard: publication retries cannot
    clobber a row that has already moved on."""
    if to_status == "delivering":
        values = {
            "status": "delivering",
            "publish_attempts": OutboxEvent.publish_attempts + 1,
        }
        from_status = "pending"
    elif to_status == "published":
        values = {"status": "published", "published_at": utcnow()}
        from_status = "delivering"
    elif to_status == "pending":
        values = {"status": "pending", "last_error": (error or "")[:512]}
        from_status = "delivering"
    res = db.execute(
        update(OutboxEvent).where(OutboxEvent.id == event.id, OutboxEvent.status == from_status).values(**values)
    )
    db.commit()
    return bool(res.rowcount)


# --------------------------------------------------------------------------- #
# Finalization

def _outcome(task: TaskRun, outcome: str) -> dict:
    return {
        "task_id": task.id,
        "outcome": outcome,
        "status": task.status,
        "stage": task.stage,
        "attempts": task.attempts,
    }


def skip(reason: str, task: TaskRun | None = None) -> dict:
    out: dict = {"outcome": "skipped", "reason": reason}
    if task is not None:
        out["task_id"] = task.id
        out["status"] = task.status
    return out


def _finalize_success(db: Session, task: TaskRun, result: dict) -> dict:
    task.status = "succeeded"
    task.stage = "done"
    task.result = dict(result or {})
    task.error_code = None
    task.error_detail = None
    task.lease_owner = None
    task.lease_expires_at = None
    if task.grant_source == "approval" and task.grant_id:
        db.query(ActionApproval).filter_by(id=task.grant_id).update({"used_at": utcnow()})
    audit(db, "task.succeeded", task.user_id, object_id=task.id, actor="worker")
    db.commit()
    return _outcome(task, "succeeded")


def _finalize_cancelled(db: Session, task: TaskRun) -> dict:
    task.status = "cancelled"
    task.stage = "cancelled_" + (task.stage or "unknown")
    task.lease_owner = None
    task.lease_expires_at = None
    audit(db, "task.cancelled", task.user_id, object_id=task.id, actor="worker")
    db.commit()
    return _outcome(task, "cancelled")


def _finalize_failed(
    db: Session,
    task: TaskRun,
    code: str,
    detail: str,
    *,
    permanent: bool,
    actor: str = "worker",
    detail_meta: dict | None = None,
) -> dict:
    task.status = "failed"
    task.stage = "failed"
    task.error_code = code
    task.error_detail = (detail or "")[:2000]
    task.lease_owner = None
    task.lease_expires_at = None
    audit(db, "task.failed", task.user_id, object_id=task.id, actor=actor,
          detail={"code": code, "permanent": permanent, **(detail_meta or {})})
    db.commit()
    return _outcome(task, "failed")


def _finalize_retry(db: Session, task: TaskRun, code: str, detail: str) -> dict:
    if task.attempts >= task.max_attempts:
        detail = detail or "attempts exhausted"
        meta = {"code": code, "attempts": task.attempts}
        return _finalize_failed(db, task, code, detail, permanent=True, detail_meta=meta)
    delay = backoff(task.attempts)
    task.status = "queued"
    task.stage = f"retry_attempt_{task.attempts}"
    task.error_code = code
    task.error_detail = (detail or "")[:2000]
    task.lease_owner = None
    task.lease_expires_at = None
    task.next_attempt_at = utcnow() + timedelta(seconds=delay)
    db.add(OutboxEvent(task_id=task.id, event_type="deliver"))
    audit(db, "task.retried", task.user_id, object_id=task.id, actor="worker",
          detail={"code": code, "attempt": task.attempts, "delay_s": round(delay, 3)})
    db.commit()
    return _outcome(task, "retry_scheduled")


def backoff(attempt: int) -> float:
    """Jittered exponential backoff (attempt starts at 1)."""
    settings = get_settings()
    delay = settings.wf_retry_base_s * math.pow(2, max(attempt - 1, 0))
    if settings.wf_retry_jitter > 0:
        delay *= 1.0 + random.uniform(0, settings.wf_retry_jitter)
    return min(delay, 3600.0)
