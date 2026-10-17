"""Task handler registry + execution context.

Later features (discovery, optimization, submission, email) register work here
without changing the worker core. Handlers declare whether performing them
would cause external side effects; side-effect handlers require an approval or
automation policy at execution time (workflows.authorization), and that check
runs again on every attempt.
"""

import time
from datetime import timedelta
from typing import Any, Callable

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.workflows.clock import utcnow
from app.workflows.models import TaskRun


class TaskFailure(Exception):
    """Transient failure: retried with finite backoff until max_attempts."""

    def __init__(self, code: str = "task_failed", detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


class TaskPermanentFailure(TaskFailure):
    """Invalid input or non-transient predicate failure: never retried."""


class HandlerSpec:
    __slots__ = ("runnable", "external_side_effect", "summary")

    def __init__(self, runnable, external_side_effect: bool, summary: str):
        self.runnable = runnable
        self.external_side_effect = external_side_effect
        self.summary = summary


class TaskContext:
    """Handler-facing helpers: heartbeats, cancellation, task row access."""

    __slots__ = ("db", "task", "worker_id")

    def __init__(self, db: Session, task: TaskRun, worker_id: str = "inline"):
        self.db = db
        self.task = task
        self.worker_id = worker_id

    def heartbeat(self, progress: dict | None = None) -> None:
        """Extend the current lease so lease recovery does not requeue us."""
        now = utcnow()
        self.task.heartbeat_at = now
        self.task.lease_expires_at = now + timedelta(seconds=get_settings().wf_lease_seconds)
        if progress is not None:
            self.task.progress = progress
        self.db.commit()

    def cancelled(self) -> bool:
        return bool(self.task.cancel_requested)

    def set_progress(self, progress: dict) -> None:
        self.task.progress = progress
        self.task.heartbeat_at = utcnow()
        self.db.commit()


_REGISTRY: dict[str, HandlerSpec] = {}


def register(kind: str, external_side_effect: bool = False, summary: str = "") -> Callable:
    """Decorator: register a handler implementation under `kind`."""

    def _wrap(fn: Callable[[dict, TaskContext], dict]) -> Callable[[dict, TaskContext], dict]:
        if kind in _REGISTRY:
            raise ValueError(f"task handler {kind!r} is already registered")
        _REGISTRY[kind] = HandlerSpec(fn, external_side_effect, summary)
        return fn

    return _wrap


def get_handler(kind: str) -> HandlerSpec | None:
    return _REGISTRY.get(kind)


def known_kinds() -> list[str]:
    return sorted(_REGISTRY)


def run_task(kind: str, payload: dict, ctx: TaskContext) -> dict:
    spec = _REGISTRY.get(kind)
    if spec is None:
        raise TaskPermanentFailure("unknown_kind", f"no handler registered for kind {kind!r}")
    return spec.runnable(payload, ctx)


# --------------------------------------------------------------------------
# Built-in diagnostic handler (step 02). Harmless by construction: bounded
# sleep, echoes its own payload, and injects failures so retries/backoff,
# leases and cancellation can be exercised without any external service.
# --------------------------------------------------------------------------


@register("diagnostics.echo", summary="Echoes its payload; optional bounded sleep and injected failures")
def _diagnostics_echo(payload: dict, ctx: TaskContext) -> dict:
    message = str(payload.get("message", ""))
    sleep_s = max(0.0, min(float(payload.get("sleep_s", 0.0) or 0.0), 10.0))
    ctx.set_progress({"stage": "echo"})
    if sleep_s:
        time.sleep(sleep_s)
    fail = str(payload.get("fail", "never"))
    fail_times = int(payload.get("fail_times", 1) or 0)
    marker = payload.get("attempt_marker")
    attempts_used = int(marker) if marker is not None else int(ctx.task.attempts)
    if fail == "permanent":
        raise TaskPermanentFailure("diagnostics_permanent", "injected permanent failure")
    if fail == "transient" and attempts_used < fail_times:
        raise TaskFailure("diagnostics_transient", "injected transient failure")
    return {"echo": message, "slept_s": sleep_s, "attempts_used": attempts_used}


def _unused_any(*_a: Any, **_k: Any) -> None:  # pragma: no cover
    """Kept for future handler categories; avoids accidental broad usage."""
