"""Opportunity schemas — request/response contracts for ranking and prospects.

`description` is null for startup prospects: the API never returns a synthetic
job description. `competition` keeps the measurement meaning with the count.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class VacancyCreateIn(BaseModel):
    job_id: str


class StartupCreateIn(BaseModel):
    url: str
    name: str | None = None
    note: str | None = None


class StartupSearchIn(BaseModel):
    query: str
    limit: int = Field(default=10, ge=1, le=50)


class EvaluateIn(BaseModel):
    weights: dict | None = None


class ApplicantCountIn(BaseModel):
    count: int = Field(ge=0)
    platform: str | None = None
    source: str | None = None
    observed_at: datetime | None = None
    meaning: str = "unknown"
    note: str | None = None


class ExcludeIn(BaseModel):
    excluded: bool
    reason: str | None = None


class OrganizationOut(BaseModel):
    id: str
    name: str | None = None
    domain: str | None = None
    website: str | None = None
    location: str | None = None
    sources: list = Field(default_factory=list)


class ObservationOut(BaseModel):
    id: str
    observed_count: int
    platform: str | None = None
    source: str | None = None
    observed_at: str | None = None
    meaning: str = "unknown"
    comparable: bool = False
    note: str | None = None


class OpportunityItemOut(BaseModel):
    id: str
    kind: str
    has_listing: bool
    title: str | None = None
    company: str | None = None
    domain: str | None = None
    location: str | None = None
    eligibility: dict
    fit: dict
    competition: dict
    potentially_overlooked: bool = False
    priority_score: float | None = None
    excluded: bool = False
    exclusion_reason: str | None = None
    created_at: str | None = None


class OpportunityListOut(BaseModel):
    items: list[OpportunityItemOut] = Field(default_factory=list)
    total: int = 0
    next_cursor: str | None = None


class OpportunityDetailOut(OpportunityItemOut):
    description: str | None = None
    organization: OrganizationOut | None = None
    job: dict | None = None
    first_seen_at: str | None = None
    source_evidence: list = Field(default_factory=list)
    evaluation: dict | None = None
    observations: list[ObservationOut] = Field(default_factory=list)
    application: dict | None = None


class SaveOut(BaseModel):
    id: str
    opportunity_id: str
    kind: str
    company: str
    role: str
    location: str | None = None
    job_url: str | None = None
    status: str
    date_saved: str | None = None
    has_listing: bool
    raw_jd: str
    status_history: list = Field(default_factory=list)
    created_at: str | None = None


class SaveResultOut(BaseModel):
    application: SaveOut
    created: bool


class EvaluationOut(BaseModel):
    id: str
    opportunity_id: str
    evaluation_no: int
    eligibility: dict
    fit: dict
    competition: dict
    signals: list = Field(default_factory=list)
    priority: dict
    config: dict
    created_at: str | None = None


class StartupLeadOut(BaseModel):
    name: str | None = None
    domain: str | None = None
    website: str
    evidence: list = Field(default_factory=list)


class StartupSearchOut(BaseModel):
    provider: str
    configured: str
    leads: list[StartupLeadOut] = Field(default_factory=list)


class ProvidersOut(BaseModel):
    configured: str
    available: list[str] = Field(default_factory=list)
