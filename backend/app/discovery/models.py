"""Discovery domain tables (step 03).

`JobListing` is the canonical, deduplicated vacancy (scoped to its owner per
spec §8: discovery records start user-owned). `ListingSource` preserves every
observation from every source; `DiscoveryRun` records scan outcomes and the
counters that explain creates/updates/closures/review flags.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base, TimestampMixin, uuid_key as _uuid

DISCOVERY_ADAPTERS = ("greenhouse", "lever", "company_careers")
LISTING_STATUSES = ("active", "closed")
RUN_STATUSES = ("running", "succeeded", "failed")
MATCH_METHODS = ("external_id", "canonical_url", "fuzzy", "new")


class DiscoverySource(Base, TimestampMixin):
    """A configured feed/board/careers page an owner wants scanned."""

    __tablename__ = "discovery_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    adapter: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Adapter-specific shape, e.g. {"url": ..., "company_name": ...}.
    config: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=720)
    #: Per-run listing budget (upper bound on observations processed).
    max_listings: Mapped[int] = mapped_column(Integer, nullable=False, default=100)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Adapter cursor for resumable/paginated boards.
    cursor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    __table_args__ = (
        CheckConstraint("interval_minutes >= 5", name="ck_discovery_sources_interval"),
        CheckConstraint(
            "max_listings >= 1 AND max_listings <= 1000", name="ck_discovery_sources_budget"
        ),
        Index("ix_discovery_sources_owner_enabled_next", "owner_id", "enabled", "next_run_at"),
    )


class JobListing(Base, TimestampMixin):
    """Canonical deduplicated vacancy (one per real job, however seen)."""

    __tablename__ = "job_listings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company_name: Mapped[str] = mapped_column(String(300), nullable=False)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    remote_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    employment_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=None
    )
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    #: Which rule closed it, e.g. "absent_complete_scans" (spec §3).
    closed_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Consecutive successful complete scans the listing was absent from.
    absent_scans: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    canonical_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    apply_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Fuzzy match too uncertain to auto-merge (spec §3: goes to review).
    needs_review: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: The listing this one is a suspected duplicate of, when needs_review.
    review_candidate_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        CheckConstraint("status IN ('active', 'closed')", name="ck_job_listings_status"),
        Index("ix_job_listings_owner_status", "owner_id", "status"),
        Index("ix_job_listings_owner_canonical", "owner_id", "canonical_url"),
    )


class ListingSource(Base, TimestampMixin):
    """One source's observation of a listing; preserves every reference."""

    __tablename__ = "listing_sources"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    listing_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("job_listings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discovery_sources.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    #: External listing ID as the source publishes it (nullable by design).
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    apply_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: How this observation attached to its listing (spec dedup order).
    match_method: Mapped[str] = mapped_column(String(32), nullable=False, default="new")
    match_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_listing_sources_source_external"),
    )


class DiscoveryRun(Base, TimestampMixin):
    """Outcome of one scan of one source (success or failure)."""

    __tablename__ = "discovery_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("discovery_sources.id", ondelete="CASCADE"), nullable=False, index=True
    )
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    trigger: Mapped[str] = mapped_column(String(16), nullable=False, default="manual")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pages_fetched: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    seen_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    closed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("status IN ('running', 'succeeded', 'failed')", name="ck_discovery_runs_status"),
        CheckConstraint("trigger IN ('manual', 'scheduled')", name="ck_discovery_runs_trigger"),
    )
