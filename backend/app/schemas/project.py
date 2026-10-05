"""Project recommendation schemas — future work is NEVER mixed with evidence."""

from pydantic import BaseModel, Field


class ProjectRecommendation(BaseModel):
    project_name: str
    problem_statement: str = ""
    skills_covered: list[str] = Field(default_factory=list)
    architecture: str = ""
    features: list[str] = Field(default_factory=list)
    why_it_closes_the_gap: str = ""
    interview_topics: list[str] = Field(default_factory=list)
    estimated_complexity: str = "medium"  # low | medium | high
    missing_after_project: list[str] = Field(default_factory=list)
