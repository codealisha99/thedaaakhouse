"""Contracts for offline, editable outreach drafts."""

from typing import Literal

from pydantic import BaseModel, Field


class DraftCreateIn(BaseModel):
    opportunity_id: str
    recipient_email: str = Field(min_length=3, max_length=320)
    recipient_name: str | None = Field(default=None, max_length=256)
    recipient_role: str | None = Field(default=None, max_length=256)
    recipient_identity: Literal["known", "unknown"] = "unknown"
    contact_source_url: str | None = None
    contact_source_kind: Literal["published", "provider_reported", "inferred_pattern", "user_supplied"] = "user_supplied"
    evidence_ids: list[str] = Field(default_factory=list, max_length=10)
    resume_version_id: str | None = None


class DraftPatchIn(BaseModel):
    recipient_email: str | None = Field(default=None, min_length=3, max_length=320)
    recipient_name: str | None = Field(default=None, max_length=256)
    recipient_role: str | None = Field(default=None, max_length=256)
    recipient_identity: Literal["known", "unknown"] | None = None
    contact_source_url: str | None = None
    contact_source_kind: Literal["published", "provider_reported", "inferred_pattern", "user_supplied"] | None = None
    subject: str | None = Field(default=None, min_length=1, max_length=998)
    body: str | None = Field(default=None, min_length=1, max_length=20000)
    resume_version_id: str | None = None


class DraftOut(BaseModel):
    id: str
    opportunity_id: str
    mode: str
    recipient_email: str
    recipient_name: str | None
    recipient_role: str | None
    recipient_identity: str
    contact_source_url: str | None
    contact_source_kind: str
    subject: str
    body: str
    personalization: dict
    factuality_findings: list
    resume_version_id: str | None
    attachment_name: str | None
    attachment_preview: str | None
    attachment_sha256: str | None
    payload_sha256: str
    revision: int
    status: str
    approval_invalidated: bool = False

