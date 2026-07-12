"""
app/apps/schema.py

Pydantic schemas for Apps module.
"""

import uuid
from typing import Optional, Any
from pydantic import BaseModel, Field, ConfigDict

from app.apps.model import AppType, AppStatus


class AppBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    type: AppType = Field(default=AppType.WEB)
    domain: Optional[str] = Field(None, max_length=500)
    settings: dict[str, Any] = Field(default_factory=dict)


class AppCreate(AppBase):
    company_id: uuid.UUID


class AppUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    slug: Optional[str] = Field(None, min_length=1, max_length=255, pattern=r"^[a-z0-9-]+$")
    type: Optional[AppType] = None
    status: Optional[AppStatus] = None
    domain: Optional[str] = Field(None, max_length=500)
    settings: Optional[dict[str, Any]] = None


class AppResponse(AppBase):
    id: uuid.UUID
    company_id: uuid.UUID
    status: AppStatus
    api_key: str
    
    model_config = ConfigDict(from_attributes=True)


class AppListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[AppResponse]
