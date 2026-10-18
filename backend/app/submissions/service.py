"""Submission service — prepare, freeze, queue, execute, reconcile.

Flow (specification.md §7, build-prompts step 07):

1. ``prepare`` builds the package preview: selected resume text, required
   form questions (sensitive ones never inferred), destination, adapter
   availability. Missing mandatory answers => ``needs_input`` with the list.
2. ``queue_submission`` freezes the package (answers + exact resume text +
   hashes), rejects the manual-handoff adapter with an actionable next step,
   creates a one-shot payload-bound approval, and enqueues the durable task.
   Idempotent: the same package under the same key replays the original
   submission; a different package under the same key conflicts (409).
3. The worker handler re-checks everything immediately before the external
   effect: package hash, artifact hash (a changed resume fails fast),
   adapter availability, authorization still valid — then calls the adapter.
   Ambiguous timeouts land in ``unknown`` state and are resolved by
   reconciliation — never blind resubmission.
4. Only a confirmed receipt sets the application to ``applied``, and the
   receipt carries the exact submitted artifact hash. Manual provenance is
   untouched.
"""

import hashlib
from datetime import timedelta  # noqa: F401 — kept for TTL math clarity

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db import models
from app.submissions.adapters import (
    Adapter,
    AdapterUnavailable,
    SubmissionRejected,
    SubmissionTimeout,
    available_adapters,  # noqa: F401 — re-exported for routes/doc use
    build,
    selection_for,
)
from app.submissions.models import ACTIVE_STATES, ApplicationSubmission
from app.workflows.automation import AutomationService
from app.workflows.clock import utcnow
from app.workflows.handlers import (
    TaskContext,
    TaskFailure,
    TaskPermanentFailure,
    register,
)
from app.workflows.models import TaskRun
from app.workflows.service import TaskConflict, TaskService, audit, payload_hash

log = get_logger(__name__)

ACTION_KIND = "submissions.execute"

MANUAL_HANDOFF_INSTRUCTION = (
    "Open the apply form at the destination URL in a browser and paste the "
    "prepared answers exactly. The frozen package and resume are kept on the "
    "application; mark the application applied yourself when done."
)


class SubmissionError(ValueError):
    """422-able error with a stable code for the API layer."""

    def __init__(self, code: str, detail: str):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


# --------------------------------------------------------------------------- #
# Package construction (pure — no rows written)

def normalize_questions(questions: list[dict] | None, adapter: Adapter) -> list[dict]:
    """Snapshot the form. Caller-declared questions must be well-formed;
    otherwise the adapter's declared required set is used. Sensitive screeners
    are a required-set problem, not a prefill problem."""
    if not questions:
        return [dict(q) for q in (adapter.required_questions or [])]
    normalized: list[dict] = []
    seen: set[str] = set()
    for q in questions:
        if not isinstance(q, dict) or not q.get("id"):
            raise SubmissionError("invalid_question", "each question needs a non-empty id")
        qid = str(q["id"])
        if qid in seen:
            raise SubmissionError("invalid_question", f"duplicate question id {qid!r}")
        seen.add(qid)
        normalized.append(
            {
                "id": qid,
                "label": str(q.get("label", qid)),
                "required": bool(q.get("required", False)),
            }
        )
    return normalized


def sha256_text(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def _artifact_for(
    db: Session,
    user_id: str,
    application: models.Application,
    resume_version_id: str | None,
) -> tuple[str, str, str, str | None]:
    """Resolve the exact resume text to submit and its hash. Prefers the
    requested version (must be owner-scoped), then the application's attached
    version, then the master resume. Never synthesizes content."""
    version: models.ResumeVersion | None = None
    if resume_version_id:
        v = db.get(models.ResumeVersion, resume_version_id)
        if v is None or v.user_id != user_id:
            raise SubmissionError("resume_not_found", "resume version not found")
        version = v
    elif application.resume_version_id:
        version = db.get(models.ResumeVersion, application.resume_version_id)
    if version is not None:
        if version.user_id != user_id:
            raise SubmissionError("resume_not_found", "resume version not found")
        text = version.content or ""
        return text, sha256_text(text), "version", version.id
    master = (
        db.query(models.Resume)
        .filter_by(user_id=user_id)
        .order_by(models.Resume.created_at.desc())
        .first()
    )
    if master is None or not (master.raw_text or "").strip():
        raise SubmissionError("resume_missing", "no resume available to submit")
    text = master.raw_text or ""
    return text, sha256_text(text), "master", None


def build_package(
    db: Session,
    user_id: str,
    application: models.Application,
    *,
    answers: dict | None,
    destination_url: str | None,
    resume_version_id: str | None,
    questions: list[dict] | None,
    adapter_kind: str | None = None,
) -> dict:
    """Freeze everything needed to submit — and nothing else. This dict is
    hashed and stored verbatim; edits create a different package."""
    if not destination_url or not str(destination_url).strip():
        raise SubmissionError("destination_required", "a destination apply URL is required")
    destination = str(destination_url).strip()
    if not (destination.startswith("http://") or destination.startswith("https://")):
        raise SubmissionError("destination_invalid", "destination must be an http(s) URL")
    if answers is not None and not isinstance(answers, dict):
        raise SubmissionError("invalid_answers", "answers must be an object")

    kind, adapter = selection_for(destination)
    if adapter_kind is not None and adapter_kind != kind:
        raise SubmissionError(
            "adapter_not_available",
            f"adapter {adapter_kind!r} is not available for this destination; "
            f"resolved adapter is {kind!r}",
        )

    form = normalize_questions(questions, adapter)
    required_ids = [q["id"] for q in form if q["required"]]
    answers_in = {k: str(v) for k, v in (answers or {}).items() if v is not None}
    missing = [qid for qid in required_ids if not answers_in.get(qid, "").strip()]

    artifact_text, artifact_sha256, resume_source, selected_version_id = _artifact_for(
        db, user_id, application, resume_version_id
    )
    package = {
        "application_id": application.id,
        "company": application.company,
        "role": application.role,
        "destination_url": destination,
        "adapter": kind,
        "resume_version_id": selected_version_id,
        "resume_source": resume_source,
        "form": form,
        "answers": answers_in,
        "required_missing": missing,
    }
    return {
        "package": package,
        "package_sha256": payload_hash(package),
        "artifact_sha256": artifact_sha256,
        "artifact_text": artifact_text,
        "adapter_kind": kind,
        "adapter": adapter,
        "missing": missing,
        "state": "needs_input" if missing else "ready",
    }


# --------------------------------------------------------------------------- #
# Service

class SubmissionService:
    """Owner-scoped operations; every method re-validates ownership."""

    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id
        self.settings = get_settings()

    def _get_owned(self, model, obj_id: str):
        obj = self.db.get(model, obj_id)
        if obj is None or getattr(obj, "user_id", None) != self.user_id:
            return None
        return obj

    def get(self, submission_id: str) -> ApplicationSubmission | None:
        return self._get_owned(ApplicationSubmission, submission_id)

    def list_for(self, application_id: str) -> list[ApplicationSubmission]:
        return (
            self.db.query(ApplicationSubmission)
            .filter_by(user_id=self.user_id, application_id=application_id)
            .order_by(ApplicationSubmission.created_at.desc())
            .all()
        )

    # ------------------------------------------------------------------ #
    # Queue (request side)

    def queue_submission(
        self,
        application_id: str,
        *,
        answers: dict | None,
        destination_url: str | None,
        resume_version_id: str | None,
        questions: list[dict] | None,
        idempotency_key: str | None,
        ttl_seconds: int | None = None,
    ) -> tuple[ApplicationSubmission, TaskRun, bool]:
        """Freeze + authorize + enqueue (or replay). Returns (submission, task, replayed)."""
        application = self._get_owned(models.Application, application_id)
        if application is None:
            raise SubmissionError("application_not_found", "application not found")
        destination_url = destination_url or application.job_url

        built = build_package(
            self.db,
            self.user_id,
            application,
            answers=answers,
            destination_url=destination_url,
            resume_version_id=resume_version_id,
            questions=questions,
        )
        if built["missing"]:
            raise SubmissionError(
                "needs_input",
                "unanswered required questions: " + ", ".join(built["missing"]),
            )

        # The idempotency key names one immutable request for its full
        # lifetime, including after a terminal result. Replaying a completed
        # request must never create a second external submission.
        if idempotency_key:
            prior = (
                self.db.query(ApplicationSubmission)
                .filter_by(user_id=self.user_id, idempotency_key=idempotency_key)
                .first()
            )
            if prior is not None:
                if prior.package_sha256 != built["package_sha256"]:
                    raise SubmissionError(
                        "idempotency_conflict",
                        "this idempotency key was already used with a different package",
                    )
                task = self.db.get(TaskRun, prior.task_id) if prior.task_id else None
                return prior, task, True

        kind = built["adapter_kind"]
        if kind == "manual":
            raise SubmissionError("manual_handoff", MANUAL_HANDOFF_INSTRUCTION)

        existing = self._find_active(application_id, built["package_sha256"])
        if existing is not None:
            if idempotency_key and existing.idempotency_key and existing.idempotency_key != idempotency_key:
                raise SubmissionError(
                    "idempotency_conflict",
                    "this idempotency key belongs to a different submission",
                )
            task = self.db.get(TaskRun, existing.task_id) if existing.task_id else None
            return existing, task, True

        sub = ApplicationSubmission(
            user_id=self.user_id,
            application_id=application.id,
            adapter=kind,
            state="ready",
            package=built["package"],
            package_sha256=built["package_sha256"],
            artifact_snapshot=built["artifact_text"],
            artifact_sha256=built["artifact_sha256"],
            resume_version_id=built["package"]["resume_version_id"],
            resume_source=built["package"]["resume_source"],
            destination_url=built["package"]["destination_url"],
            idempotency_key=idempotency_key or None,
        )
        audit(
            self.db, "submission.prepared", self.user_id,
            object_type="submission", object_id=sub.id,
            detail={
                "application_id": application.id,
                "adapter": kind,
                "package_sha256": sub.package_sha256,
            },
        )
        self.db.add(sub)
        try:
            self.db.commit()
        except IntegrityError:
            # Concurrent requests can race both the idempotency constraint
            # and the one-active-package constraint. Resolve either against
            # the winning row and preserve the same replay/conflict contract.
            self.db.rollback()
            prior = None
            if idempotency_key:
                prior = (
                    self.db.query(ApplicationSubmission)
                    .filter_by(user_id=self.user_id, idempotency_key=idempotency_key)
                    .first()
                )
            if prior is None:
                prior = self._find_active(application_id, built["package_sha256"])
            if prior is None:
                raise
            if prior.package_sha256 != built["package_sha256"]:
                raise SubmissionError(
                    "idempotency_conflict",
                    "this idempotency key was already used with a different package",
                ) from None
            task = self.db.get(TaskRun, prior.task_id) if prior.task_id else None
            return prior, task, True
        self.db.refresh(sub)

        # The worker payload is minimal and stable; its hash is what the
        # approval binds, so edits elsewhere cannot ride an old grant.
        task_payload = {"submission_id": sub.id, "package_sha256": sub.package_sha256}
        approver = AutomationService(self.db, self.user_id)
        try:
            approval = approver.create_approval(
                ACTION_KIND,
                task_payload,
                ttl_seconds=int(
                    ttl_seconds if ttl_seconds is not None else self.settings.submission_ttl_s
                ),
                object_ref={"application_id": application.id, "submission_id": sub.id},
                artifact_hash=sub.artifact_sha256,
            )
        except Exception as exc:  # approvals validate kinds/ttl strictly
            mark, cancelled = self.cancel_queued(sub, reason="approval_failed: " + str(exc))
            raise SubmissionError("approval_failed", str(exc)) from None

        tasks = TaskService(self.db, self.user_id)
        task, replayed_task = tasks.enqueue(
            ACTION_KIND,
            task_payload,
            idempotency_key=f"submission:{sub.id}",
        )
        sub.task_id = task.id
        sub.state = "queued"
        audit(
            self.db, "submission.queued", self.user_id,
            object_type="submission", object_id=sub.id,
            detail={"task_id": task.id, "approval_id": approval.id},
        )
        self.db.commit()
        self.db.refresh(sub)
        return sub, task, False

    def _find_active(self, application_id: str, package_sha256: str) -> ApplicationSubmission | None:
        return (
            self.db.query(ApplicationSubmission)
            .filter(
                ApplicationSubmission.user_id == self.user_id,
                ApplicationSubmission.application_id == application_id,
                ApplicationSubmission.package_sha256 == package_sha256,
                ApplicationSubmission.state.in_(ACTIVE_STATES),
            )
            .order_by(ApplicationSubmission.created_at.desc())
            .first()
        )

    # ------------------------------------------------------------------ #
    # State transitions

    def cancel_queued(self, sub: ApplicationSubmission, reason: str) -> bool:
        """Cancel a not-yet-confirmed submission; cancel the bound task too."""
        result = self.db.execute(
            update(ApplicationSubmission)
            .where(
                ApplicationSubmission.id == sub.id,
                ApplicationSubmission.user_id == self.user_id,
                ApplicationSubmission.state.in_(("ready", "queued")),
            )
            .values(state="cancelled", state_reason=reason)
        )
        if not result.rowcount:
            self.db.refresh(sub)
            return False
        audit(
            self.db, "submission.cancelled", self.user_id,
            object_type="submission", object_id=sub.id, detail={"reason": reason[:120]},
        )
        self.db.commit()
        self.db.refresh(sub)
        return True

    def mark_terminal(
        self,
        sub: ApplicationSubmission,
        state: str,
        reason: str,
        receipt: dict | None = None,
    ) -> None:
        sub.state = state
        sub.state_reason = (reason or "")[:512]
        if receipt is not None:
            sub.receipt = receipt
            sub.submitted_at = utcnow()
        self.db.commit()
        self.db.refresh(sub)

    def confirm_applied(self, sub: ApplicationSubmission, receipt: dict | None) -> None:
        """Confirmed submission: the application becomes applied ONLY here."""
        application = self.db.get(models.Application, sub.application_id)
        if application is None or application.user_id != sub.user_id:
            return
        today = utcnow().date().isoformat()
        if application.status != "applied":
            hist = list(application.status_history or [])
            hist.append(
                {
                    "from": application.status,
                    "to": "applied",
                    "at": today,
                    "via": f"submission:{sub.id}",
                }
            )
            application.status_history = hist
            application.status = "applied"
            application.date_applied = today
        self.db.commit()

    # ------------------------------------------------------------------ #
    # Reconciliation (resolution of unknown states)

    def reconcile(self, submission_id: str, outcome: str) -> ApplicationSubmission:
        """Resolve an ``unknown`` submission.

        ``outcome="check"`` asks the configured adapter's receipt endpoint
        (get-receipt hook). ``outcome="absent"`` records the destination's
        affirmative "we never received it". Neither ever re-sends.
        """
        sub = self.get(submission_id)
        if sub is None:
            raise SubmissionError("submission_not_found", "submission not found")
        if outcome == "absent":
            if sub.state not in ("unknown",):
                raise SubmissionError("not_reconcilable", f"submission state is {sub.state!r}")
            self.mark_terminal(sub, "failed", "destination has no record of this submission")
            audit(
                self.db, "submission.reconciled_absent", sub.user_id,
                object_type="submission", object_id=sub.id, actor="system",
            )
            return sub

        if sub.state != "unknown":
            raise SubmissionError("not_reconcilable", f"submission state is {sub.state!r}")
        adapter = build(sub.adapter)
        if (
            adapter is None
            or not adapter.live
            or adapter.reconcile_fn is None
        ):
            sub.state_reason = "no reconciliation transport configured"
            self.db.commit()
            raise SubmissionError(
                "reconcile_unavailable", adapter.reason if adapter else f"unknown adapter {sub.adapter!r}"
            )
        dest = sub.package.get("destination_url") or ""
        result = adapter.reconcile_fn(dest, sub.id)
        status = (result or {}).get("status")
        if status == "found":
            receipt = result.get("receipt") or {}
            frozen = _receipt_from(adapter.name, receipt, dest, sub)
            self.mark_terminal(sub, "submitted", "", receipt=frozen)
            self.confirm_applied(sub, frozen)
            audit(
                self.db, "submission.reconciled", sub.user_id,
                object_type="submission", object_id=sub.id, actor="system",
                detail={"receipt_id": frozen["receipt_id"], "adapter": adapter.name},
            )
            return sub
        if status == "not_found":
            self.mark_terminal(sub, "failed", "destination has no record of this submission")
            audit(
                self.db, "submission.reconciled_absent", sub.user_id,
                object_type="submission", object_id=sub.id, actor="system",
            )
            return sub
        # unreachable/anything else: stays unknown
        sub.state_reason = "destination could not answer during reconciliation"
        self.db.commit()
        self.db.refresh(sub)
        return sub


def _receipt_from(provider: str, receipt: dict, dest: str, sub: ApplicationSubmission) -> dict:
    return {
        "provider": provider,
        "receipt_id": receipt.get("receipt_id"),
        "received_at": receipt.get("received_at"),
        "destination_url": dest,
        "artifact_sha256": sub.artifact_sha256,
        "payload_sha256": sub.package_sha256,
        "submission_id": sub.id,
    }


# --------------------------------------------------------------------------- #
# Worker handler

@register(
    ACTION_KIND,
    external_side_effect=True,
    summary="Submit a frozen application package through a configured adapter",
)
def _execute_submission(payload: dict, ctx: TaskContext) -> dict:
    svc = SubmissionService(ctx.db, ctx.task.user_id)
    sub = svc.get(payload.get("submission_id") or "")
    if sub is None:
        raise TaskPermanentFailure("submission_missing", "submission row not found for this task")
    if sub.package_sha256 != payload.get("package_sha256"):
        raise TaskPermanentFailure(
            "package_changed", "the frozen package hash does not match the task payload"
        )

    # Deduplicate redeliveries: terminal states never re-execute.
    if sub.state in ("submitted", "failed", "cancelled"):
        log.info("submission {} already terminal ({}) — skipping delivery", sub.id, sub.state)
        return {"outcome": "skipped", "reason": f"submission_{sub.state}"}
    if sub.state == "unknown":
        return {"outcome": "skipped", "reason": "submission_unknown_awaits_reconciliation"}

    # Immediate pre-flight re-checks (execution time, not request time).
    now = utcnow()
    res = ctx.db.execute(
        update(ApplicationSubmission)
        .where(
            ApplicationSubmission.id == sub.id,
            ApplicationSubmission.state.in_(("queued", "submitting")),
        )
        .values(
            state="submitting",
            attempts=ApplicationSubmission.attempts + 1,
            last_attempt_at=now,
        )
    )
    ctx.db.commit()
    if not res.rowcount:
        fresh = ctx.db.get(ApplicationSubmission, sub.id)
        raise TaskPermanentFailure(
            "submission_state_conflict", f"submission state is {fresh.state!r}, cannot submit"
        )
    ctx.db.refresh(sub)

    # Package provenance still holds?
    if sub.package_sha256 != payload_hash(sub.package or {}):
        svc.mark_terminal(sub, "failed", "frozen package was mutated in storage")
        raise TaskPermanentFailure("package_changed", "frozen package was mutated in storage")

    # Artifact unchanged since freeze? An edited resume invalidates queued work.
    live_sha = _live_artifact_sha256(ctx.db, sub)
    if live_sha is not None and live_sha != sub.artifact_sha256:
        reason = "the resume text changed after this submission was queued"
        svc.mark_terminal(sub, "failed", reason)
        raise TaskPermanentFailure("artifact_changed", reason)

    adapter_kind = sub.adapter or (sub.package or {}).get("adapter") or "manual"
    adapter = build(adapter_kind)
    if adapter is None or not adapter.live or adapter.submit_fn is None:
        svc.mark_terminal(sub, "failed", "no usable live transport for the adapter")
        raise TaskPermanentFailure(
            "adapter_unavailable",
            f"adapter {adapter_kind!r} has no usable live transport at execution time",
        )
    if ctx.cancelled():
        svc.mark_terminal(sub, "cancelled", "cancellation requested before external submission")
        raise TaskFailure("cancelled", "cancellation was requested")

    dest = sub.package.get("destination_url") or ""
    ext_payload = {
        "submission_id": sub.id,
        "idempotency_key": sub.id,
        "artifact_sha256": sub.artifact_sha256,
        "payload_sha256": sub.package_sha256,
        "answers": dict((sub.package or {}).get("answers") or {}),
        "resume_text": sub.artifact_snapshot or "",
    }
    ctx.heartbeat({"stage": "submitting", "adapter": adapter.name})
    try:
        receipt = adapter.submit_fn(ext_payload, dest, sub.id)
    except SubmissionRejected as exc:
        if exc.transient:
            sub.state = "queued"  # stay non-terminal for the bounded retry
            sub.state_reason = exc.detail
            ctx.db.commit()
            raise TaskFailure(exc.code, exc.detail) from None
        svc.mark_terminal(sub, "failed", exc.detail)
        raise TaskPermanentFailure(exc.code, exc.detail) from None
    except SubmissionTimeout as exc:
        # Ambiguous: the destination may have processed it. No resubmission.
        svc.mark_terminal(sub, "unknown", exc.detail or "ambiguous timeout after sending")
        raise TaskPermanentFailure("submission_unknown", exc.detail) from None

    if not isinstance(receipt, dict) or "receipt_id" not in receipt:
        svc.mark_terminal(sub, "failed", "destination returned a malformed receipt")
        raise TaskPermanentFailure(
            "invalid_receipt", "destination returned a malformed receipt"
        )

    frozen = _receipt_from(adapter.name, receipt, dest, sub)
    svc.mark_terminal(sub, "submitted", "", receipt=frozen)
    svc.confirm_applied(sub, frozen)
    audit(
        ctx.db, "submission.confirmed", sub.user_id,
        object_type="submission", object_id=sub.id, actor="worker",
        detail={"receipt_id": frozen["receipt_id"], "adapter": adapter.name},
    )
    return {
        "outcome": "submitted",
        "submission_id": sub.id,
        "receipt_id": frozen["receipt_id"],
        "application_id": sub.application_id,
    }


def _live_artifact_sha256(db: Session, sub: ApplicationSubmission) -> str | None:
    """Current hash of the linked resume version, to re-verify the frozen
    artifact at execution time. Master-only snapshots have no live source —
    the master itself is a frozen upload, so nothing to compare."""
    if sub.resume_source == "version" and sub.resume_version_id:
        version = db.get(models.ResumeVersion, sub.resume_version_id)
        if version is None:
            return None
        return sha256_text(version.content or "")
    return None
