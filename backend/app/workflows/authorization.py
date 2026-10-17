"""Execution-time authorization for external-side-effect tasks.

Two independent authority sources, checked immediately before execution and
re-validated on every attempt:

- ``ActionApproval``: one payload-bound, expiring approval for a single action.
  Becomes invalid when payload/artifact changes, is revoked, or has expired.
- ``AutomationPolicy``: a standing permission with allowed action kinds,
  optional expiry and a concurrency-safe, windowed quota reservation (row
  lock in ``reserve_quota``) so parallel workers cannot exceed the limit.

The first successful reservation binds the grant onto the task row
(``grant_source``/``grant_id``); retries reuse it without counting quota
again, but fail if their grant was revoked or expired mid-flight.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.workflows.clock import aware, utcnow
from app.workflows.models import (
    ActionApproval,
    AutomationPolicy,
    POLICY_ACTIVE,
    TaskRun,
)
from app.workflows.service import audit


class AuthorizationDenied(Exception):
    """Stable-code rejection consumed by the executor to fail the task."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


@dataclass
class Grant:
    source: str  # "approval" | "policy"
    id: str


def _not_expired(expires_at, now) -> bool:
    return expires_at is None or aware(expires_at) > now


def reserve_quota(db: Session, policy: AutomationPolicy, kind: str, now: datetime) -> bool:
    """Reserve one unit of the policy's windowed quota for `kind`.

    Locks the policy row so concurrent workers serialize; returns True when
    a unit was reserved (counter incremented, committed with the executor's
    transaction) and False when the limit is already used this window.
    """
    limits = policy.constraints or {}
    try:
        limit = int(limits.get("daily_limit", 0) or 0)
    except (TypeError, ValueError):
        limit = 0
    if limit <= 0:
        raise AuthorizationDenied(
            "policy_invalid", f"policy {policy.id} has no positive daily_limit"
        )
    window = int(limits.get("window_seconds", 86400) or 86400)

    db.query(AutomationPolicy).filter_by(id=policy.id).with_for_update().first()
    db.refresh(policy)  # counters re-read after the lock
    counters = dict(policy.counters or {})

    reset = True
    window_start = counters.get("window_start")
    if window_start:
        try:
            start = aware(
                window_start if isinstance(window_start, datetime) else datetime.fromisoformat(window_start)
            )
            reset = now >= start + timedelta(seconds=window)
        except ValueError:
            reset = False
    counts = {} if reset else dict(counters.get("counts", {}))
    used = int(counts.get(kind, 0) or 0)
    if used >= limit:
        db.commit()  # release the row lock; no reservation happened
        return False
    counts[kind] = used + 1
    policy.counters = {
        "window_start": now.isoformat() if reset else counters.get("window_start"),
        "counts": counts,
    }
    db.add(policy)
    db.commit()
    return True


def authorize_action(
    db: Session,
    user_id: str,
    kind: str,
    p_hash: str,
    task: TaskRun,
) -> Grant:
    """Validate + consume authority for executing `kind` with payload `p_hash`.

    Called by the executor immediately before each attempt. Raises
    AuthorizationDenied with a stable error code when not permitted.
    """
    now = utcnow()

    if task.grant_source and task.grant_id:
        return _revalidate_grant(db, kind, p_hash, task, now)

    approvals = (
        db.query(ActionApproval)
        .filter_by(user_id=user_id, action_kind=kind, payload_hash=p_hash)
        .order_by(ActionApproval.created_at.asc())
        .all()
    )
    for approval in approvals:
        if approval.status != "active" or not _not_expired(approval.expires_at, now):
            continue
        if approval.task_id and approval.task_id != task.id:
            raise AuthorizationDenied(
                "approval_used_by_other_task", "approval already bound to another task"
            )
        approval.task_id = task.id
        task.grant_source = "approval"
        task.grant_id = approval.id
        audit(db, "task.authorized", user_id, object_id=task.id,
              detail={"source": "approval", "grant_id": approval.id}, actor="worker")
        db.commit()
        return Grant(source="approval", id=approval.id)

    policies = (
        db.query(AutomationPolicy)
        .filter_by(user_id=user_id, status=POLICY_ACTIVE)
        .order_by(AutomationPolicy.created_at.asc())
        .all()
    )
    exhausted: list[str] = []
    for policy in policies:
        if not _not_expired(policy.expires_at, now):
            continue
        if kind not in (policy.allowed_actions or []):
            continue
        try:
            ok = reserve_quota(db, policy, kind, now)
        except AuthorizationDenied as exc:
            raise AuthorizationDenied(f"policy_invalid::{policy.id}", exc.detail) from None
        if ok:
            task.grant_source = "policy"
            task.grant_id = policy.id
            audit(db, "task.authorized", user_id, object_id=task.id,
                  detail={"source": "policy", "grant_id": policy.id}, actor="worker")
            db.commit()
            return Grant(source="policy", id=policy.id)
        exhausted.append(policy.id)

    if exhausted:
        raise AuthorizationDenied(
            "quota_exhausted", "automation policy quota for this window is already used"
        )
    raise AuthorizationDenied(
        "no_active_authorization", f"no active approval or policy permits action {kind!r}"
    )


def _revalidate_grant(db: Session, kind: str, p_hash: str, task: TaskRun, now: datetime) -> Grant:
    """A retry still holds its original grant; confirm it stayed valid."""
    if task.grant_source == "approval":
        approval = db.get(ActionApproval, task.grant_id)
        if (
            approval is None
            or approval.status != "active"
            or not _not_expired(approval.expires_at, now)
            or approval.task_id != task.id
            or approval.payload_hash != p_hash
            or approval.action_kind != kind
        ):
            raise AuthorizationDenied(
                "authorization_revoked",
                "the approval used for this task is no longer valid for this payload",
            )
        return Grant(source="approval", id=approval.id)

    policy = db.get(AutomationPolicy, task.grant_id)
    if (
        policy is None
        or policy.status != POLICY_ACTIVE
        or not _not_expired(policy.expires_at, now)
        or kind not in (policy.allowed_actions or [])
    ):
        raise AuthorizationDenied(
            "authorization_revoked", "the policy used for this task is no longer active"
        )
    return Grant(source="policy", id=policy.id)
