"""Durable workflow tables — authoritative task state lives in the database.

Design (specification.md §7):
- ``task_runs``: every queued unit of work, with attempts, lease and result.
- ``outbox_events``: written in the SAME transaction as the task change; a
  dispatcher publishes them to the queue, so a crash after commit can never
  lose accepted work.
- ``audit_events``: who did what to which object, redacted detail only.
- ``automation_policies`` / ``action_approvals``: bounded, revocable,
  expiring authority for actions with external side effects.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base, TimestampMixin

TASK_STATUSES = ("queued", "running", "succeeded", "failed", "cancelled")

OUTBOX_PENDING = "pending"
OUTBOX_PUBLISHED = "published"

POLICY_ACTIVE = "active"
POLICY_REVOKED = "revoked"

APPROVAL_ACTIVE = "active"
APPROVAL_CONSUMED = "consumed"
APPROVAL_REVOKED = "revoked"
APPROVAL_EXPIRED = "expired"


def _uuid() -> str:
    return str(uuid.uuid4())


class TaskRun(Base, TimestampMixin):
    """One logical task. Unique (user, kind, idempotency_key) when a key is given."""

    __tablename__ = "task_runs"
    __table_args__ = (
        UniqueConstraint("user_id", "kind", "idempotency_key", name="uq_task_runs_idem"),
        Index("ix_task_runs_status_due", "status", "next_attempt_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    kind: Mapped[str] = mapped_column(String(120))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64))

    status: Mapped[str] = mapped_column(String(32), default="queued")
    stage: Mapped[str] = mapped_column(String(120), default="created")
    progress: Mapped[dict] = mapped_column(JSON, default=dict)

    attempts: Mapped[int] = mapped_column(default=0)
    max_attempts: Mapped[int] = mapped_column(default=5)

    next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lease_owner: Mapped[str | None] = mapped_column(String(120), nullable=True)
    lease_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(default=False)

    # Authority consumed at first attempt; reused (not re-reserved) on retries.
    grant_source: Mapped[str | None] = mapped_column(String(16), nullable=True)
    grant_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class OutboxEvent(Base, TimestampMixin):
    """Queue delivery record. Pending rows are (re)published by the dispatcher,
    making task commits survive worker/queue crashes."""

    __tablename__ = "outbox_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(64), default="deliver")
    status: Mapped[str] = mapped_column(String(16), default=OUTBOX_PENDING, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    publish_attempts: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str | None] = mapped_column(String(512), nullable=True)


class AuditEvent(Base, TimestampMixin):
    """Append-only record of significant task/automation actions (no payloads)."""

    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(64), default="system")
    action: Mapped[str] = mapped_column(String(128), index=True)
    object_type: Mapped[str] = mapped_column(String(64), default="")
    object_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)


class AutomationPolicy(Base, TimestampMixin):
    """Owner-scoped standing permission for bounded automated actions."""

    __tablename__ = "automation_policies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(255))
    allowed_actions: Mapped[list] = mapped_column(JSON, default=list)
    constraints: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(32), default=POLICY_ACTIVE, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    counters: Mapped[dict] = mapped_column(JSON, default=dict)


class ActionApproval(Base, TimestampMixin):
    """One-shot payload-bound approval: becomes invalid if the payload changes."""

    __tablename__ = "action_approvals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    action_kind: Mapped[str] = mapped_column(String(120))
    object_ref: Mapped[dict] = mapped_column(JSON, default=dict)
    payload_hash: Mapped[str] = mapped_column(String(64))
    artifact_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default=APPROVAL_ACTIVE, index=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
