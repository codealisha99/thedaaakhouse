"""Job description models — raw text in, structured requirements out."""

from typing import Literal

from pydantic import BaseModel, Field

RequirementStatus = Literal["matched", "partial", "missing", "uncertain"]


class JobRequirement(BaseModel):
    requirement: str
    category: str = "general"  # e.g. skill | technology | domain | qualification
    importance: str = "medium"  # high | medium | low
    evidence_needed: str = ""


class JobDescription(BaseModel):
    title: str = "Untitled role"
    company: str | None = None
    location: str | None = None
    experience_level: str | None = None
    responsibilities: list[str] = Field(default_factory=list)
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    domain: str | None = None
    raw_text: str = ""
    source_url: str | None = None


class RequirementMatch(BaseModel):
    """One requirement evaluated against the candidate profile.

    NOTE: `confidence` is internal only. Never show a bare number to the user
    unless the scoring methodology is documented and visible.
    """

    requirement: str
    status: RequirementStatus
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0


class JobCreate(BaseModel):
    title: str = "Untitled role"
    company_name: str | None = None
    source_url: str | None = None
    location: str | None = None
    raw_text: str


class JobOut(BaseModel):
    id: str
    title: str
    company_name: str | None = None
    source_url: str | None = None
    location: str | None = None
    status: str
    structured: JobDescription | None = None

    model_config = {"from_attributes": True}
