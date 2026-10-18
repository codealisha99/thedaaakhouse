"""Submission schemas — contracts for package preparation and submission.

The package preview includes only what the user should see; the frozen
package on the submission row is the data the worker submits.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.submissions.models import SUBMISSION_STATES


class QuestionOut(BaseModel):
    id: str
    label: str = ""
    required: bool = False


class AdapterCapabilityOut(BaseModel):
    kind: str
    live: bool
    reason: str


class HandoffOut(BaseModel):
    url: str
    instruction: str


class PrepareIn(BaseModel):
    answers: dict | None = None
    destination_url: str | None = None
    resume_version_id: str | None = None
    questions: list[QuestionOut] | None = None
    adapter: str | None = None


class PrepareOut(BaseModel):
    application_id: str
    adapter: AdapterCapabilityOut
    destination_url: str
    questions: list[QuestionOut]
    answers: dict
    missing_required: list[str]
    package_sha256: str
    artifact_sha256: str
    artifact_preview: str
    state: Literal["ready", "needs_input", "error"]
    handoff: HandoffOut | None = None
    error: str | None = None


class SubmitIn(BaseModel):
    answers: dict | None = None
    destination_url: str | None = None
    resume_version_id: str | None = None
    questions: list[QuestionOut] | None = None
    idempotency_key: str = Field(min_length=1, max_length=255)
    ttl_seconds: int | None = Field(default=None, gt=0, le=86400)


class SubmissionOut(BaseModel):
    id: str
    application_id: str
    adapter: str
    state: str
    state_reason: str
    destination_url: str | None
    package_sha256: str
    artifact_sha256: str
    resume_version_id: str | None
    resume_source: str
    receipt: dict | None
    task_id: str | None
    idempotency_key: str | None
    attempts: int
    created_at: datetime
    submitted_at: datetime | None


class SubmitQueuedOut(BaseModel):
    submission_id: str
    task_id: str | None
    status: str
    poll_url: str
    replayed: bool
    state: str


class SubmissionListOut(BaseModel):
    application_id: str
    submissions: list[SubmissionOut]
    total: int


class ReconcileIn(BaseModel):
    outcome: Literal["check", "absent"]


class ReconcileOut(BaseModel):
    submission_id: str
    state: str
    resolution: str
    note: str = ""


def submission_out(sub) -> dict:
    if sub.created_at.tzinfo is None:
        created = sub.created_at.isoformat() + "Z"
    else:
        created = sub.created_at.isoformat()
    submitted = None
    if sub.submitted_at is not None:
        submitted = (
            sub.submitted_at.isoformat() + "Z"
            if sub.submitted_at.tzinfo is None
            else sub.submitted_at.isoformat()
        )
    return {
        "id": sub.id,
        "application_id": sub.application_id,
        "adapter": sub.adapter,
        "state": sub.state,
        "state_reason": sub.state_reason or "",
        "destination_url": sub.destination_url,
        "package_sha256": sub.package_sha256,
        "artifact_sha256": sub.artifact_sha256,
        "resume_version_id": sub.resume_version_id,
        "resume_source": sub.resume_source,
        "receipt": sub.receipt,
        "task_id": sub.task_id,
        "idempotency_key": sub.idempotency_key,
        "attempts": sub.attempts or 0,
        "created_at": created,
        "submitted_at": submitted,
    }
