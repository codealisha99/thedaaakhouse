"""Application submissions — the recorded history of package-level sends.

One row per submission attempt of a frozen package:

- immutable payload/artifact hashes (and a full artifact snapshot) are frozen
  at request time and re-verified by the worker before any external effect;
- ``state`` follows the specification's machine:
  ``ready → queued → submitting → submitted | failed | unknown`` (plus
  ``cancelled`` on user cancellation);
- only a confirmed receipt marks the parent application as applied, and the
  receipt carries the exact submitted artifact hash;
- user idempotency keys replay the original submission; a different package
  under the same key conflicts (409 upstream).
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base, TimestampMixin

SUBMISSION_STATES = (
    "ready",
    "queued",
    "submitting",
    "submitted",
    "failed",
    "unknown",
    "cancelled",
)

# Non-terminal states: replayed/queued attempts that must dedupe.
ACTIVE_STATES = ("ready", "queued", "submitting", "unknown")
_ACTIVE_SQL = "state IN ('ready','queued','submitting','unknown')"


def _uuid() -> str:
    return str(uuid.uuid4())


class ApplicationSubmission(Base, TimestampMixin):
    """One submission of one frozen application package."""

    __tablename__ = "application_submissions"
    __table_args__ = (
        UniqueConstraint("user_id", "idempotency_key", name="uq_submissions_idem"),
        Index(
            "uq_submissions_active_package",
            "user_id",
            "application_id",
            "package_sha256",
            unique=True,
            sqlite_where=text(_ACTIVE_SQL),
            postgresql_where=text(_ACTIVE_SQL),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    application_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("applications.id"), index=True
    )

    adapter: Mapped[str] = mapped_column(String(64))
    state: Mapped[str] = mapped_column(String(32), default="ready", index=True)
    state_reason: Mapped[str] = mapped_column(Text, default="")

    # Frozen package: answers, questions, destination, resume reference.
    package: Mapped[dict] = mapped_column(JSON)
    package_sha256: Mapped[str] = mapped_column(String(64), index=True)

    # The exact submitted artifact: text snapshot + its hash, frozen at
    # request time (the live ResumeVersion can be edited later; this cannot).
    artifact_snapshot: Mapped[str] = mapped_column(Text)
    artifact_sha256: Mapped[str] = mapped_column(String(64), index=True)
    resume_version_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("resume_versions.id"), nullable=True
    )

    resume_source: Mapped[str] = mapped_column(String(32), default="version")
    destination_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    task_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)

    receipt: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_attempt_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    attempts: Mapped[int] = mapped_column(default=0)
