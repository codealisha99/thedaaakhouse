"""Task + automation schemas (step 02 contracts)."""

from pydantic import BaseModel, ConfigDict, Field


class TaskCreate(BaseModel):
    kind: str = Field(min_length=1, max_length=120)
    payload: dict = Field(default_factory=dict)
    # Idempotency may also arrive as the Idempotency-Key header; body wins.
    idempotency_key: str | None = Field(default=None, max_length=128)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    status: str
    stage: str
    attempts: int
    max_attempts: int
    next_attempt_at: str | None = None
    result: dict | None = None
    error_code: str | None = None
    error_detail: str | None = None
    progress: dict = Field(default_factory=dict)
    cancel_requested: bool = False
    grant_source: str | None = None
    created_at: str = ""
    updated_at: str = ""
    poll_url: str = ""


class TaskQueueOut(BaseModel):
    """202 Accepted body per specification.md §9."""

    task_id: str
    status: str
    poll_url: str
    replayed: bool = False


class TaskCancelOut(BaseModel):
    id: str
    status: str
    stage: str | None = None
    cancel_requested: bool


class TaskStatsOut(BaseModel):
    tasks: dict[str, int] = Field(default_factory=dict)
    pending_outbox_events: int = 0


class KindsOut(BaseModel):
    kinds: list[str]
