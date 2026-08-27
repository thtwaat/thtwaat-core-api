"""app/coding_agent/schemas.py — Phase 6C-1/6C-2 request/response models."""

from __future__ import annotations

from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator


class ServiceTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    scope: str


# ---------------------------------------------------------------------------
# Phase 6C-2 — task-creation proxy
# ---------------------------------------------------------------------------

MAX_GOAL_CHARS = 20_000


class CodingBudgetSpec(BaseModel):
    """Mirrors AI_Project's own api.schemas.BudgetSpec bounds exactly —
    Core re-validates rather than trusting AI_Project's own 400 alone,
    so an oversized request is rejected at Core's boundary too."""

    max_turns: Optional[int] = Field(default=None, ge=1, le=200)
    max_tool_calls: Optional[int] = Field(default=None, ge=1, le=1000)
    max_cost_usd: Optional[float] = Field(default=None, ge=0, le=1000)
    max_execution_seconds: Optional[float] = Field(default=None, gt=0, le=14_400)


class CodingTaskCreateRequest(BaseModel):
    """No company_id/user_id/owner field — identity is ALWAYS the
    authenticated Core session (app.auth.router.get_current_user), same
    discipline AI_Project's own TaskCreateRequest already holds itself
    to. No project_id either: the workspace is derived entirely from the
    Core identity's ServiceLinkStore mapping on the AI_Project side."""

    goal: str = Field(..., min_length=1, max_length=MAX_GOAL_CHARS)
    budget: Optional[CodingBudgetSpec] = None

    @field_validator("goal")
    @classmethod
    def _check_goal(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("goal must not be blank")
        return v


class CodingTaskResponse(BaseModel):
    """Core's OWN stable response shape — deliberately not a pass-through
    of AI_Project's JSON, so a future AI_Project internal change doesn't
    silently change what Studio receives from Core."""

    task_id: str
    status: str
    phase: Optional[str] = None
    termination_code: Optional[str] = None
    created_at: float
    updated_at: float
    started_at: Optional[float] = None
    ended_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None


class CodingTaskCancelResponse(BaseModel):
    task_id: str
    status: str
    cancel_requested: bool
    message: str
