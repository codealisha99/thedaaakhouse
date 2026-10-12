"""Learning Hub schemas."""

from pydantic import BaseModel


class PlanCreate(BaseModel):
    application_id: str
    resume_id: str | None = None
    title: str | None = None


class AnswerIn(BaseModel):
    topic: str
    answer: str


class TopicStatusIn(BaseModel):
    topic: str
    status: str
