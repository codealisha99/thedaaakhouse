"""Versioned, owner-scoped outreach drafts. Drafts never send email."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base, TimestampMixin, uuid_key as _uuid


class OutreachDraft(Base, TimestampMixin):
    __tablename__ = "outreach_drafts"
    __table_args__ = (Index("ix_outreach_drafts_user_opportunity", "user_id", "opportunity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[str] = mapped_column(String(36), ForeignKey("opportunities.id", ondelete="CASCADE"), index=True)
    mode: Mapped[str] = mapped_column(String(16), nullable=False)
    recipient_email: Mapped[str] = mapped_column(String(320), nullable=False)
    recipient_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    recipient_role: Mapped[str | None] = mapped_column(String(256), nullable=True)
    recipient_identity: Mapped[str] = mapped_column(String(24), nullable=False)
    contact_source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    contact_source_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    subject: Mapped[str] = mapped_column(String(998), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    personalization: Mapped[dict] = mapped_column(JSON, nullable=False)
    factuality_findings: Mapped[list] = mapped_column(JSON, nullable=False)
    resume_version_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("resume_versions.id", ondelete="SET NULL"), nullable=True)
    attachment_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    attachment_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    approval_payload_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)


class OutreachDraftVersion(Base, TimestampMixin):
    __tablename__ = "outreach_draft_versions"
    __table_args__ = (UniqueConstraint("draft_id", "revision", name="uq_outreach_draft_revision"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    draft_id: Mapped[str] = mapped_column(String(36), ForeignKey("outreach_drafts.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    payload_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
