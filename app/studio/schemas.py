"""Pydantic schemas for THTWAAT Studio."""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.studio.models import StudioProjectStatus


class StudioProjectCreate(BaseModel):
    prompt: str = Field(..., min_length=8, max_length=20_000)
    title: Optional[str] = Field(None, max_length=255)

    @field_validator("prompt")
    @classmethod
    def strip_prompt(cls, value: str) -> str:
        cleaned = (value or "").strip()
        if len(cleaned) < 8:
            raise ValueError("Prompt must be at least 8 characters")
        return cleaned

    @field_validator("title")
    @classmethod
    def strip_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class StudioProjectResponse(BaseModel):
    id: UUID
    workspace_id: UUID
    user_id: Optional[UUID] = None
    title: str
    prompt: str
    status: StudioProjectStatus
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class StudioProjectListResponse(BaseModel):
    items: list[StudioProjectResponse]
    total: int
