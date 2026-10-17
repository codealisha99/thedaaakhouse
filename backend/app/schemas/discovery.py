"""Pydantic schemas for the discovery API."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

AdapterName = Literal["greenhouse", "lever", "company_careers"]


class SourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200, examples=["Acme Greenhouse board"])
    adapter: AdapterName
    config: dict[str, Any] = Field(
        default_factory=dict,
        examples=[{"url": "https://boards.greenhouse.io/acme", "company_name": "Acme"}],
    )
    interval_minutes: int = Field(default=720, ge=5, le=10_080)
    max_listings: int = Field(default=100, ge=1, le=1000)
    enabled: bool = True


class SourcePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    config: dict[str, Any] | None = None
    interval_minutes: int | None = Field(default=None, ge=5, le=10_080)
    max_listings: int | None = Field(default=None, ge=1, le=1000)
    enabled: bool | None = None


class SourceOut(BaseModel):
    id: str
    name: str
    adapter: str
    config: dict[str, Any]
    enabled: bool
    interval_minutes: int
    max_listings: int
    next_run_at: datetime | None
    last_run_at: datetime | None
    last_success_at: datetime | None
    consecutive_failures: int
    created_at: datetime

    model_config = {"from_attributes": True}


class RunCreate(BaseModel):
    source_id: str


class RunOut(BaseModel):
    id: str
    source_id: str
    status: str
    trigger: str
    started_at: datetime
    finished_at: datetime | None
    pages_fetched: int
    seen_count: int
    created_count: int
    updated_count: int
    closed_count: int
    review_count: int
    error_code: str | None
    error_detail: str | None

    model_config = {"from_attributes": True}


class ListingSourceOut(BaseModel):
    source_id: str
    external_id: str | None
    source_url: str
    apply_url: str | None
    posted_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime
    match_method: str
    match_score: float | None

    model_config = {"from_attributes": True}


class ListingOut(BaseModel):
    id: str
    status: str
    title: str
    company_name: str
    location: str | None
    remote_mode: str | None
    employment_type: str | None
    posted_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime | None
    closed_at: datetime | None
    closed_reason: str | None
    canonical_url: str | None
    apply_url: str | None
    needs_review: bool
    review_candidate_id: str | None
    sources: list[ListingSourceOut] = Field(default_factory=list)

    model_config = {"from_attributes": True}
