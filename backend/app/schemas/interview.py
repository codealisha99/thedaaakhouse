"""Interview prep schemas — questions are always tied to their reason."""

from pydantic import BaseModel, Field


class InterviewQuestion(BaseModel):
    question: str
    category: str  # coding | system_design | behavioral | resume_specific | ...
    reason: str  # why this question was generated
    source: str = ""  # e.g. candidate_project | jd_requirement | company_research


class PreparationPlan(BaseModel):
    topics: list[str] = Field(default_factory=list)
    questions: list[InterviewQuestion] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)


class ArenaStart(BaseModel):
    mode: str = "mock"
    difficulty: str = "medium"
    application_id: str | None = None
    resume_id: str | None = None


class ArenaAnswer(BaseModel):
    answer: str
