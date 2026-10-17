"""Automation policy + approval schemas."""

from pydantic import BaseModel, Field


class PolicyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    allowed_actions: list[str] = Field(min_length=1)
    constraints: dict = Field(default_factory=dict)
    ttl_seconds: int | None = None  # minutes-to-live alternative to expires_at
    expires_at: str | None = None


class PolicyUpdate(BaseModel):
    daily_limit: int = Field(gt=0)
    revoke: bool = False


class PolicyOut(BaseModel):
    id: str
    name: str
    allowed_actions: list[str]
    constraints: dict
    status: str
    expires_at: str | None = None
    revoked_at: str | None = None
    created_at: str = ""


class ApprovalCreate(BaseModel):
    action_kind: str = Field(min_length=1, max_length=120)
    payload: dict = Field(default_factory=dict)
    ttl_seconds: int = Field(gt=0, le=86400)
    object_ref: dict = Field(default_factory=dict)
    artifact_hash: str | None = Field(default=None, max_length=64)


class ApprovalOut(BaseModel):
    id: str
    action_kind: str
    object_ref: dict
    payload_hash: str
    artifact_hash: str | None = None
    status: str
    expires_at: str | None = None
    used_by_task: str | None = None
    revoked_at: str | None = None
    created_at: str = ""


class PolicyUsageOut(BaseModel):
    policy_id: str
    window_start: str | None = None
    counts: dict = Field(default_factory=dict)
    daily_limit: int = 0
