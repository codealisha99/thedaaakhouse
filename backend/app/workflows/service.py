"""TaskService — creation, polling, cancellation of durable tasks.

Guarantees (specification.md §7):
- Task + outbox event are written in ONE transaction; the dispatcher publishes
  pending outbox rows, so a crash after commit can only re-publish, never lose.
- Accepts an owner-scoped Idempotency-Key: replay of the same key + payload
  returns the original task; same key with a different payload is a conflict
  (mapped to HTTP 409). Concurrent duplicate requests race on the unique
  constraint and collapse into one logical task.
"""

import hashlib
import json

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.workflows import handlers
from app.workflows.models import AuditEvent, OutboxEvent, TaskRun

log = get_logger(__name__)


class TaskConflict(Exception):
    def __init__(self, existing_task_id: str):
        super().__init__("idempotency key already used with a different payload")
        self.existing_task_id = existing_task_id


class UnknownKind(ValueError):
    pass


def payload_hash(payload: dict) -> str:
    """Stable hash (key order normalized) reused for approvals and conflicts."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def audit(
    db: Session,
    action: str,
    user_id: str | None,
    *,
    object_type: str = "task",
    object_id: str | None = None,
    correlation_id: str | None = None,
    actor: str = "user",
    detail: dict | None = None,
) -> None:
    """Append an audit row (no payload contents — ids/kinds/codes only)."""
    db.add(
        AuditEvent(
            user_id=user_id,
            actor=actor,
            action=action,
            object_type=object_type,
            object_id=object_id,
            correlation_id=correlation_id,
            detail=detail or {},
        )
    )


class TaskService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    # ------------------------------------------------------------------ #
    # Creation

    def enqueue(
        self,
        kind: str,
        payload: dict | None = None,
        idempotency_key: str | None = None,
        max_attempts: int | None = None,
    ) -> tuple[TaskRun, bool]:
        """Create (or idempotently replay) a task plus its outbox delivery.

        Both rows commit in one transaction. Returns (task, replayed).
        Raises UnknownKind for unregistered kinds and TaskConflict when the
        key was already used with a different payload.
        """
        payload = dict(payload or {})
        spec = handlers.get_handler(kind)
        if spec is None:
            raise UnknownKind(f"unknown task kind {kind!r}")
        hash_ = payload_hash(payload)
        key = idempotency_key or None  # empty string -> NULL -> no dedupe
        cap = int(max_attempts or get_settings().wf_max_attempts)

        task = TaskRun(
            user_id=self.user_id,
            kind=kind,
            payload=payload,
            payload_hash=hash_,
            status="queued",
            max_attempts=cap,
            idempotency_key=key,
        )
        try:
            self.db.add(task)
            self.db.flush()  # task.id assigned; still uncommitted
            event = OutboxEvent(task_id=task.id, event_type="deliver")
            self.db.add(event)
            audit(
                self.db,
                "task.created",
                self.user_id,
                object_id=task.id,
                correlation_id=task.id,
                detail={"kind": kind, "payload_hash": hash_, "external_side_effect": spec.external_side_effect},
            )
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = (
                self.db.query(TaskRun)
                .filter_by(user_id=self.user_id, kind=kind, idempotency_key=key)
                .first()
            )
            if existing is None:
                raise
            if existing.payload_hash != hash_:
                raise TaskConflict(existing.id) from None
            audit(self.db, "task.replayed", self.user_id, actor="system", object_id=existing.id)
            self.db.commit()
            return existing, True
        self.db.refresh(task)
        return task, False

    # ------------------------------------------------------------------ #
    # Polling

    def get(self, task_id: str) -> TaskRun | None:
        return self.db.query(TaskRun).filter_by(id=task_id, user_id=self.user_id).first()

    def stats(self) -> dict:
        counts: dict[str, int] = {}
        for task in self.db.query(TaskRun).filter_by(user_id=self.user_id):
            counts[task.status] = counts.get(task.status, 0) + 1
        pending = (
            self.db.query(OutboxEvent)
            .join(TaskRun, OutboxEvent.task_id == TaskRun.id)
            .filter(TaskRun.user_id == self.user_id, OutboxEvent.status == "pending")
            .count()
        )
        return {"tasks": counts, "pending_outbox_events": pending}

    # ------------------------------------------------------------------ #
    # Cancellation

    def cancel(self, task_id: str) -> tuple[TaskRun, bool]:
        """Request cancellation. Still-queued tasks are cancelled outright;
        running ones get `cancel_requested`, which the executor honors between
        stages (external effects already accepted cannot be undone)."""
        task = self.get(task_id)
        if task is None:
            raise LookupError("task not found")
        if task.status in ("succeeded", "failed", "cancelled"):
            return task, False
        if task.status == "queued":
            task.status = "cancelled"
            task.stage = "cancelled_before_start"
            audit(self.db, "task.cancelled", self.user_id, object_id=task.id, detail={"phase": "queued"})
            self.db.commit()
            return task, True
        task.cancel_requested = True
        audit(self.db, "task.cancel_requested", self.user_id, object_id=task.id)
        self.db.commit()
        return task, True
