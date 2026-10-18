"""Deterministic, offline outreach draft preparation and revisioning."""

import hashlib
import json
import re
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.db import models
from app.outreach.models import OutreachDraft, OutreachDraftVersion
from app.workflows.clock import utcnow
from app.workflows.models import APPROVAL_ACTIVE, APPROVAL_REVOKED, ActionApproval
from app.workflows.service import audit

log = get_logger(__name__)
_EMAIL = re.compile(r"^[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+$")


class DraftError(ValueError):
    def __init__(self, code: str, detail: str):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _hash(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def _validate_email(value: str) -> str:
    value = (value or "").strip()
    if not _EMAIL.fullmatch(value):
        raise DraftError("invalid_recipient", "recipient_email must be a valid email address")
    return value


def _validate_source_url(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    try:
        parsed = urlparse(value.strip())
    except ValueError:
        parsed = None
    if parsed is None or parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise DraftError("invalid_source_url", "contact source must be an http(s) URL")
    return value.strip()


class OutreachService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def get(self, draft_id: str) -> OutreachDraft | None:
        return self.db.query(OutreachDraft).filter_by(id=draft_id, user_id=self.user_id).first()

    def list_for_user(self) -> list[OutreachDraft]:
        return (self.db.query(OutreachDraft).filter_by(user_id=self.user_id)
                .order_by(OutreachDraft.updated_at.desc()).all())

    def create(self, *, opportunity_id: str, recipient_email: str,
               recipient_name: str | None, recipient_role: str | None,
               recipient_identity: str, contact_source_url: str | None,
               contact_source_kind: str, evidence_ids: list[str],
               resume_version_id: str | None) -> OutreachDraft:
        opportunity = self.db.query(models.Opportunity).filter_by(
            id=opportunity_id, user_id=self.user_id
        ).first()
        if opportunity is None:
            raise DraftError("opportunity_not_found", "opportunity not found")
        organization = self.db.get(models.Organization, opportunity.organization_id)
        if organization is None or organization.user_id != self.user_id:
            raise DraftError("opportunity_not_found", "opportunity not found")
        recipient_email = _validate_email(recipient_email)
        source_url = _validate_source_url(contact_source_url)
        if recipient_identity == "known" and (not recipient_name or not source_url):
            raise DraftError("identity_source_required", "a known recipient requires a name and source URL")
        if contact_source_kind == "inferred_pattern":
            recipient_identity = "unknown"
        evidence = self._confirmed_evidence(evidence_ids)
        resume = self._resume(resume_version_id)
        content = self._generate(opportunity, recipient_name, recipient_role, recipient_identity,
                                 evidence, resume, source_url, contact_source_kind)
        draft = OutreachDraft(
            user_id=self.user_id, opportunity_id=opportunity.id,
            mode="vacancy" if opportunity.kind == "vacancy" else "startup_introduction",
            recipient_email=recipient_email, recipient_name=recipient_name,
            recipient_role=recipient_role, recipient_identity=recipient_identity,
            contact_source_url=source_url, contact_source_kind=contact_source_kind,
            subject=content["subject"], body=content["body"],
            personalization=content["personalization"],
            factuality_findings=content["factuality_findings"],
            resume_version_id=resume.id if resume else None,
            attachment_name=resume.label if resume else None,
            attachment_text=resume.content if resume else None,
            attachment_sha256=_sha_text(resume.content) if resume else None,
            payload_sha256="", revision=1, status="draft",
        )
        self.db.add(draft)
        self.db.flush()
        draft.payload_sha256 = _hash(self._as_payload(draft))
        self._snapshot(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft

    def edit(self, draft: OutreachDraft, changes: dict) -> tuple[OutreachDraft, bool]:
        snapshot = self._as_payload(draft)
        old_hash = draft.payload_sha256
        if "recipient_email" in changes:
            if changes["recipient_email"] is None:
                raise DraftError("invalid_recipient", "recipient_email cannot be empty")
            changes["recipient_email"] = _validate_email(changes["recipient_email"])
        if "contact_source_url" in changes:
            changes["contact_source_url"] = _validate_source_url(changes["contact_source_url"])
        if any(changes.get(key) is None for key in ("recipient_identity", "contact_source_kind", "subject", "body") if key in changes):
            raise DraftError("invalid_edit", "identity, source kind, subject and body cannot be null")
        if "recipient_email" in changes and "recipient_identity" not in changes:
            changes["recipient_identity"] = "unknown"
        identity = changes.get("recipient_identity", draft.recipient_identity)
        source_kind = changes.get("contact_source_kind", draft.contact_source_kind)
        name = changes.get("recipient_name", draft.recipient_name)
        source_url = changes.get("contact_source_url", draft.contact_source_url)
        if source_kind == "inferred_pattern":
            identity = "unknown"
            changes["recipient_identity"] = identity
        if identity == "known" and (not name or not source_url):
            raise DraftError("identity_source_required", "a known recipient requires a name and source URL")

        new_resume = None
        if "resume_version_id" in changes:
            new_resume = self._resume(changes["resume_version_id"])
            draft.resume_version_id = new_resume.id if new_resume else None
            draft.attachment_name = new_resume.label if new_resume else None
            draft.attachment_text = new_resume.content if new_resume else None
            draft.attachment_sha256 = _sha_text(new_resume.content) if new_resume else None
        for key in ("recipient_email", "recipient_name", "recipient_role", "recipient_identity",
                    "contact_source_url", "contact_source_kind", "subject", "body"):
            if key in changes:
                setattr(draft, key, changes[key])

        personalization = dict(draft.personalization or {})
        personalization["recipient"] = {
            "identity": draft.recipient_identity,
            "name": draft.recipient_name if draft.recipient_identity == "known" else None,
            "identity_verified": False,
            "role": draft.recipient_role,
            "source_url": draft.contact_source_url,
            "source_kind": draft.contact_source_kind,
        }
        draft.personalization = personalization
        findings = [f for f in (draft.factuality_findings or [])
                    if f.get("code") not in {"recipient_identity_unknown", "recipient_identity_unverified", "recipient_inferred", "recipient_source_missing"}]
        if draft.recipient_identity != "known":
            findings.append({"code": "recipient_identity_unknown", "detail": "The recipient identity is not verified; review the address before any later send."})
        else:
            findings.append({"code": "recipient_identity_unverified", "detail": "A source was supplied, but this system has not independently verified the person-to-address match."})
        if draft.contact_source_kind == "inferred_pattern":
            findings.append({"code": "recipient_inferred", "detail": "This address follows an inferred pattern and is not verified."})
        if not draft.contact_source_url:
            findings.append({"code": "recipient_source_missing", "detail": "No source URL was supplied for the recipient."})

        # Source metadata stays outside the email body. User-edited copy is
        # always surfaced for review; no LLM or fetched page can add claims.
        if draft.body != snapshot["body"] or draft.subject != snapshot["subject"]:
            findings = [f for f in findings if f.get("code") != "edited_copy_review"]
            findings.append({"code": "edited_copy_review", "detail": "Edited email text requires factual review before any later send."})
        draft.factuality_findings = findings
        content = self._as_payload(draft)
        draft.payload_sha256 = _hash(content)
        draft.revision += 1
        approval_invalidated = False
        if old_hash != draft.payload_sha256:
            active = self.db.query(ActionApproval).filter_by(
                user_id=self.user_id, status=APPROVAL_ACTIVE
            ).all()
            for approval in active:
                if (approval.object_ref or {}).get("draft_id") != draft.id:
                    continue
                approval.status = APPROVAL_REVOKED
                approval.revoked_at = utcnow()
                audit(self.db, "outreach.approval_invalidated", self.user_id,
                      object_type="approval", object_id=approval.id,
                      detail={"draft_id": draft.id, "revision": draft.revision})
                approval_invalidated = True
        if old_hash != draft.payload_sha256 and draft.approval_payload_sha256 is not None:
            draft.approval_payload_sha256 = None
        self._snapshot(draft)
        self.db.commit()
        self.db.refresh(draft)
        return draft, approval_invalidated

    def _confirmed_evidence(self, ids: list[str]) -> list[models.CandidateEvidence]:
        if not ids:
            return []
        if len(ids) != len(set(ids)):
            raise DraftError("invalid_evidence", "duplicate evidence ids are not allowed")
        rows = (self.db.query(models.CandidateEvidence)
                .filter(models.CandidateEvidence.user_id == self.user_id,
                        models.CandidateEvidence.id.in_(ids),
                        models.CandidateEvidence.status == "confirmed").all())
        if len(rows) != len(ids):
            raise DraftError("invalid_evidence", "each candidate fact must be owned and confirmed")
        return rows

    def _resume(self, resume_version_id: str | None):
        if not resume_version_id:
            return None
        row = self.db.get(models.ResumeVersion, resume_version_id)
        if row is None or row.user_id != self.user_id:
            raise DraftError("resume_not_found", "resume version not found")
        return row

    def _generate(self, opportunity, name, recipient_role, identity, evidence, resume,
                  contact_source_url, contact_source_kind) -> dict:
        organization = self.db.get(models.Organization, opportunity.organization_id)
        company = (organization.name if organization and organization.name
                   else organization.domain if organization and organization.domain
                   else "the organization")
        refs = list(opportunity.source_evidence or [])
        role = opportunity.title if opportunity.kind == "vacancy" else None
        greeting = f"Hello {name.strip()}," if identity == "known" and name else "Hello,"
        lines = [greeting, ""]
        if role:
            lines.append(f"I’m reaching out about the {role} opportunity at {company}.")
            reason = {"type": "vacancy", "role": role, "company": company,
                      "source_evidence": refs[:10]}
            ask = "Would you be open to a brief conversation about the role?"
        else:
            lines.append(f"I’m reaching out to learn more about {company} and your work.")
            reason = {"type": "startup_introduction", "company": company,
                      "source_evidence": refs[:10]}
            ask = "Would you be open to a brief conversation about your work and possible ways I could contribute?"
        contributions = [{"id": row.id, "ev_ref": row.ev_ref, "kind": row.kind,
                          "assert_type": row.assert_type, "source_text": row.source_text,
                          "line_start": row.line_start, "line_end": row.line_end}
                         for row in evidence]
        for item in contributions[:2]:
            excerpt = " ".join((item["source_text"] or "").split())[:500]
            if excerpt:
                lines.extend(["", f"A relevant example from my background: {excerpt}"])
        if resume:
            lines.extend(["", "I’ve attached my resume for context."])
        lines.extend(["", ask, "", "Best,"])
        findings = []
        if identity != "known":
            findings.append({"code": "recipient_identity_unknown", "detail": "The recipient identity is not verified; review the address before any later send."})
        else:
            findings.append({"code": "recipient_identity_unverified", "detail": "A source was supplied, but this system has not independently verified the person-to-address match."})
        if contact_source_kind == "inferred_pattern":
            findings.append({"code": "recipient_inferred", "detail": "This address follows an inferred pattern and is not verified."})
        if not contact_source_url:
            findings.append({"code": "recipient_source_missing", "detail": "No source URL was supplied for the recipient."})
        if opportunity.kind == "startup_prospect":
            findings.append({"code": "no_opening_claimed", "detail": "This is a startup introduction; no job opening is asserted."})
        if not contributions:
            findings.append({"code": "no_candidate_claims", "detail": "No candidate accomplishment is included because no confirmed evidence was selected."})
        if not resume:
            findings.append({"code": "no_attachment", "detail": "No resume attachment is included."})
        findings.append({"code": "candidate_signature_missing", "detail": "No confirmed candidate name is available for the signature; add one before any later send."})
        return {
            "subject": f"Interest in {role} at {company}" if role else f"Introduction — {company}",
            "body": "\n".join(lines),
            "personalization": {
                "reason": reason,
                "contributions": contributions,
                "recipient": {"identity": identity, "name": name if identity == "known" else None,
                              "identity_verified": False, "role": recipient_role, "source_url": contact_source_url,
                              "source_kind": contact_source_kind},
                "generator": "deterministic_template_v1",
                "external_content_instructions_used": False,
            },
            "factuality_findings": findings,
        }

    def _as_payload(self, draft) -> dict:
        return {"opportunity_id": draft.opportunity_id, "mode": draft.mode,
                "recipient_email": draft.recipient_email, "recipient_name": draft.recipient_name,
                "recipient_role": draft.recipient_role, "recipient_identity": draft.recipient_identity,
                "contact_source_url": draft.contact_source_url,
                "contact_source_kind": draft.contact_source_kind, "subject": draft.subject,
                "body": draft.body, "personalization": draft.personalization or {},
                "factuality_findings": draft.factuality_findings or [],
                "resume_version_id": draft.resume_version_id,
                "attachment_sha256": draft.attachment_sha256}

    def _snapshot(self, draft, snapshot=None) -> None:
        data = snapshot if snapshot is not None else self._as_payload(draft)
        self.db.add(OutreachDraftVersion(
            draft_id=draft.id, user_id=self.user_id, revision=draft.revision,
            snapshot=data, payload_sha256=draft.payload_sha256, created_at=utcnow(),
        ))


def _sha_text(value: str | None) -> str:
    return hashlib.sha256((value or "").encode()).hexdigest()
