"""Automation management — owner-scoped policies and approvals used by the
API routes and by later features that enqueue external-side-effect work.

Policies permit bounded automated execution (allowed action kinds + quota,
optional expiry); approvals authorize exactly one payload for one action.
Both are revocable and both are re-checked at execution time by
workflows.authorization — a revoked/expired grant stops pending work.
"""

from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.workflows import handlers
from app.workflows.models import (
    ActionApproval,
    AutomationPolicy,
    POLICY_ACTIVE,
    POLICY_REVOKED,
    APPROVAL_ACTIVE,
    APPROVAL_REVOKED,
)
from app.workflows.service import payload_hash as compute_payload_hash
from app.workflows.service import audit


class AutomationError(ValueError):
    pass


class AutomationService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    # ------------------------------------------------------------------ #
    # Policies

    def create_policy(self, name: str, allowed_actions: list[str],
                      constraints: dict, ttl_seconds: int | None = None,
                      expires_at: datetime | None = None) -> AutomationPolicy:
        name = (name or "").strip()
        if not name:
            raise AutomationError("name is required")
        if not isinstance(allowed_actions, list) or not allowed_actions:
            raise AutomationError("allowed_actions must be a non-empty list")
        unknown = [k for k in allowed_actions if handlers.get_handler(k) is None]
        if unknown:
            raise AutomationError(f"unknown action kinds: {', '.join(unknown)}")
        side_effect_only = [
            k for k in allowed_actions
            if handlers.get_handler(k) is not None and not handlers.get_handler(k).external_side_effect
        ]
        if side_effect_only:
            raise AutomationError("policies permit external-side-effect kinds only")
        constraints = dict(constraints or {})
        try:
            limit = int(constraints.get("daily_limit", 0))
        except (TypeError, ValueError):
            limit = 0
        if limit <= 0:
            raise AutomationError("constraints.daily_limit must be a positive integer")
        expiry = expires_at or (None if ttl_seconds is None else _utcnow() + timedelta(seconds=ttl_seconds))
        if expiry is not None and expiry <= _utcnow():
            raise AutomationError("expiry must be in the future")
        policy = AutomationPolicy(
            user_id=self.user_id,
            name=name,
            allowed_actions=[str(k) for k in allowed_actions],
            constraints={"daily_limit": limit, "window_seconds": int(constraints.get("window_seconds", 86400) or 86400)},
            status=POLICY_ACTIVE,
            expires_at=expiry,
            counters={"window_start": None, "counts": {}},
        )
        self.db.add(policy)
        audit(self.db, "policy.created", self.user_id, object_type="automation_policy",
              object_id=policy.id, detail={"actions": policy.allowed_actions, "daily_limit": limit})
        self.db.commit()
        self.db.refresh(policy)
        return policy

    def list_policies(self) -> list[AutomationPolicy]:
        return (
            self.db.query(AutomationPolicy)
            .filter_by(user_id=self.user_id)
            .order_by(AutomationPolicy.created_at.desc())
            .all()
        )

    def get_policy(self, policy_id: str) -> AutomationPolicy | None:
        return (
            self.db.query(AutomationPolicy)
            .filter_by(id=policy_id, user_id=self.user_id)
            .first()
        )

    def update_policy_limit(self, policy_id: str, daily_limit: int) -> AutomationPolicy:
        policy = self.get_policy(policy_id)
        if policy is None:
            raise LookupError("policy not found")
        if daily_limit <= 0:
            raise AutomationError("daily_limit must be a positive integer")
        policy.constraints = {**(policy.constraints or {}), "daily_limit": daily_limit}
        audit(self.db, "policy.updated", self.user_id, object_type="automation_policy",
              object_id=policy.id, detail={"daily_limit": daily_limit})
        self.db.commit()
        return policy

    def revoke_policy(self, policy_id: str) -> AutomationPolicy | None:
        policy = self.get_policy(policy_id)
        if policy is None:
            return None
        if policy.status == POLICY_ACTIVE:
            policy.status = POLICY_REVOKED
            policy.revoked_at = _utcnow()
            audit(self.db, "policy.revoked", self.user_id, object_type="automation_policy",
                  object_id=policy.id)
            self.db.commit()
        else:
            self.db.commit()
        return policy

    # ------------------------------------------------------------------ #
    # Approvals (payload-bound)

    def create_approval(self, action_kind: str, payload: dict,
                        ttl_seconds: int | None = None, object_ref: dict | None = None,
                        artifact_hash: str | None = None) -> ActionApproval:
        spec = handlers.get_handler(action_kind)
        if spec is None:
            raise AutomationError(f"unknown action kind {action_kind!r}")
        if not spec.external_side_effect:
            raise AutomationError("approvals apply to external-side-effect kinds only")
        if not isinstance(payload, dict) or compute_payload_hash(payload) == compute_payload_hash({}):
            raise AutomationError("a non-empty payload must be bound to the approval")
        ttl = None if ttl_seconds is None else int(ttl_seconds)
        if ttl is not None and (ttl <= 0 or ttl > 24 * 3600):
            raise AutomationError("ttl_seconds must be in (0, 86400]")
        approval = ActionApproval(
            user_id=self.user_id,
            action_kind=action_kind,
            object_ref=dict(object_ref or {}),
            payload_hash=compute_payload_hash(payload),
            artifact_hash=artifact_hash,
            status=APPROVAL_ACTIVE,
            expires_at=None if ttl is None else _utcnow() + timedelta(seconds=ttl),
        )
        self.db.add(approval)
        audit(self.db, "approval.created", self.user_id, object_type="approval",
              object_id=approval.id, detail={"action_kind": action_kind})
        self.db.commit()
        self.db.refresh(approval)
        return approval

    def list_approvals(self) -> list[ActionApproval]:
        return (
            self.db.query(ActionApproval)
            .filter_by(user_id=self.user_id)
            .order_by(ActionApproval.created_at.desc())
            .all()
        )

    def get_approval(self, approval_id: str) -> ActionApproval | None:
        return (
            self.db.query(ActionApproval)
            .filter_by(id=approval_id, user_id=self.user_id)
            .first()
        )

    def revoke_approval(self, approval_id: str) -> ActionApproval | None:
        approval = self.get_approval(approval_id)
        if approval is None:
            return None
        if approval.status == APPROVAL_ACTIVE:
            approval.status = APPROVAL_REVOKED
            approval.revoked_at = _utcnow()
            audit(self.db, "approval.revoked", self.user_id, object_type="approval",
                  object_id=approval.id)
            self.db.commit()
        return approval

    # ------------------------------------------------------------------ #

    def usage(self, policy_id: str) -> dict:
        policy = self.get_policy(policy_id)
        if policy is None:
            raise LookupError("policy not found")
        counters = policy.counters or {}
        return {
            "policy_id": policy.id,
            "window_start": counters.get("window_start"),
            "counts": dict(counters.get("counts", {})),
            "daily_limit": int((policy.constraints or {}).get("daily_limit", 0)),
        }


def _utcnow() -> datetime:
    from app.workflows.clock import utcnow

    return utcnow()


def policy_out(policy: AutomationPolicy) -> dict[str, Any]:
    return {
        "id": policy.id,
        "name": policy.name,
        "allowed_actions": policy.allowed_actions or [],
        "constraints": policy.constraints or {},
        "status": policy.status,
        "expires_at": _iso(policy.expires_at),
        "revoked_at": _iso(policy.revoked_at),
        "created_at": _iso(policy.created_at),
    }


def approval_out(approval: ActionApproval) -> dict[str, Any]:
    return {
        "id": approval.id,
        "action_kind": approval.action_kind,
        "object_ref": approval.object_ref or {},
        "payload_hash": approval.payload_hash,
        "artifact_hash": approval.artifact_hash,
        "status": approval.status,
        "expires_at": _iso(approval.expires_at),
        "used_by_task": approval.task_id,
        "created_at": _iso(approval.created_at),
        "revoked_at": _iso(approval.revoked_at),
    }


def _iso(value) -> str | None:
    return value.isoformat() if value is not None else None
