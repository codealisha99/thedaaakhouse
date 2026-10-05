"""Company research schemas — every claim keeps its source."""

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    source_url: str
    source_title: str = ""
    retrieved_at: str = ""


class CompanyProfile(BaseModel):
    name: str
    website: str | None = None
    products: list[str] = Field(default_factory=list)
    business_model: str = ""
    engineering_focus: list[str] = Field(default_factory=list)
    technology_signals: list[str] = Field(default_factory=list)
    relevant_product: str = ""
    relevant_team: str = ""
    recent_developments: list[str] = Field(default_factory=list)
    role_context: str = ""
    sources: list[SourceRef] = Field(default_factory=list)


class CompanyOut(BaseModel):
    id: str
    name: str
    website: str | None = None
    profile: CompanyProfile | None = None

    model_config = {"from_attributes": True}
