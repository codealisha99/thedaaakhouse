"""Candidate profile — the structured source of truth.

Rule: downstream modules (matcher, optimizer, latex editor) may ONLY use
this validated profile, never raw resume text. Anything absent from the
profile is treated as missing, never invented.
"""

from pydantic import BaseModel, Field


class PersonalInformation(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    links: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: str
    degree: str | None = None
    field: str | None = None
    start: str | None = None
    end: str | None = None
    details: list[str] = Field(default_factory=list)


class ExperienceEntry(BaseModel):
    company: str
    title: str
    start: str | None = None
    end: str | None = None
    bullets: list[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str
    description: str = ""
    technologies: list[str] = Field(default_factory=list)
    concepts: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)


class CandidateProfile(BaseModel):
    personal_information: PersonalInformation = Field(default_factory=PersonalInformation)
    education: list[EducationEntry] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)


# ---- API shapes ----


class ResumeOut(BaseModel):
    id: str
    filename: str
    content_type: str
    parse_status: str
    parse_error: str | None = None
    profile: CandidateProfile | None = None
    created_at: str | None = None

    model_config = {"from_attributes": True}
