"""Career profile schemas. Demonstrated / claimed / to-learn stay distinct."""

from pydantic import BaseModel, Field


class CareerProfileIn(BaseModel):
    education: list[dict] = Field(default_factory=list)
    skills_demonstrated: list[str] = Field(default_factory=list)
    skills_claimed: list[str] = Field(default_factory=list)
    skills_to_learn: list[str] = Field(default_factory=list)
    experience: list[dict] = Field(default_factory=list)
    projects: list[dict] = Field(default_factory=list)
    target_roles: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    domains: list[str] = Field(default_factory=list)
    excluded_roles: list[str] = Field(default_factory=list)
    preferences: dict = Field(default_factory=dict)
    goals: list[str] = Field(default_factory=list)


class CareerProfileOut(CareerProfileIn):
    id: str
    provenance: dict = Field(default_factory=dict)


class SeedIn(BaseModel):
    resume_id: str


class OverrideIn(BaseModel):
    classification: str


class FitWeights(BaseModel):
    direction: float = 0.40
    tech_edu: float = 0.25
    transfer: float = 0.20
    progression: float = 0.15
