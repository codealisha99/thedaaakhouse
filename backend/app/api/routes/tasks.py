"""Task API — enqueue diagnostics work, poll, cancel. Spec §9:

- 202 Accepted `{task_id, status, poll_url}`; owner-scoped 404 otherwise.
- Idempotency-Key (header or body) replays the same task for the same
  payload; same key + different payload → 409 conflict with the original id.
- The generic endpoint executes registered non-side-effect kinds only;
  feature workflows create side-effect tasks through TaskService with
  policy/approval checks at execution time.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db import models
from app.db.database import get_db
from app.schemas.tasks import (
    KindsOut,
    TaskCancelOut,
    TaskCreate,
    TaskOut,
    TaskQueueOut,
    TaskStatsOut,
)
from app.workflows import handlers
from app.workflows.service import TaskConflict, TaskService, UnknownKind

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


def _service(db: Session, user: models.User) -> TaskService:
    return TaskService(db, user.id)


def _task_out(task) -> TaskOut:
    created = task.created_at.isoformat() if task.created_at else ""
    return TaskOut(
        id=task.id,
        kind=task.kind,
        status=task.status,
        stage=task.stage or "",
        attempts=task.attempts,
        max_attempts=task.max_attempts,
        next_attempt_at=task.next_attempt_at.isoformat() if task.next_attempt_at else None,
        result=task.result,
        error_code=task.error_code,
        error_detail=task.error_detail,
        progress=task.progress or {},
        cancel_requested=bool(task.cancel_requested),
        grant_source=task.grant_source,
        created_at=created,
        updated_at=updated_iso(task),
        poll_url=f"/api/tasks/{task.id}",
    )


def updated_iso(task) -> str:
    return task.updated_at.isoformat() if task.updated_at else ""


@router.get("/kinds")
def list_kinds() -> KindsOut:
    return KindsOut(kinds=handlers.known_kinds())


@router.get("/health")
def task_health(
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> TaskStatsOut:
    svc = _service(db, user)
    return TaskStatsOut(**svc.stats())


@router.post("", status_code=202)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key", max_length=128),
) -> TaskQueueOut:
    spec = handlers.get_handler(payload.kind)
    if spec is None:
        raise HTTPException(status_code=422, detail=f"unknown task kind {payload.kind!r}")
    if spec.external_side_effect:
        raise HTTPException(
            status_code=422,
            detail=(
                f"kind {payload.kind!r} has external side effects; it is queued by its"
                " own feature workflow (which enforces approval/policy checks)"
            ),
        )
    key = payload.idempotency_key or idempotency_key
    try:
        task, replayed = _service(db, user).enqueue(
            kind=payload.kind,
            payload=payload.payload,
            idempotency_key=key,
        )
    except TaskConflict as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "idempotency_conflict",
                "message": "same Idempotency-Key used with a different payload",
                "existing_task_id": exc.existing_task_id,
            },
        ) from None
    except UnknownKind as exc:  # defensive; handler existence checked above
        raise HTTPException(status_code=422, detail=str(exc)) from None
    return TaskQueueOut(
        task_id=task.id,
        status=task.status,
        poll_url=f"/api/tasks/{task.id}",
        replayed=replayed,
    )


@router.get("/{task_id}")
def get_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> TaskOut:
    task = _service(db, user).get(task_id)
    if task is None:  # other owners are indistinguishable from missing
        raise HTTPException(status_code=404, detail="task not found")
    return _task_out(task)


@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: str,
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user),
) -> TaskCancelOut:
    try:
        task, _requested = _service(db, user).cancel(task_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="task not found") from None
    return TaskCancelOut(
        id=task.id, status=task.status, stage=task.stage or None,
        cancel_requested=bool(task.cancel_requested),
    )
