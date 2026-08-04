"""Pydantic schemas for AI Product Generator."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnalyzeRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=2000)


class AnalysisResponse(BaseModel):
    industry: str
    product_type: str
    category: str
    required_features: List[str]
    brand_tone: str
    language: str
    suggested_name: str
    confidence: float
    keywords_matched: List[str] = Field(default_factory=list)
    recommended_template_slug: Optional[str] = None
    recommended_template_name: Optional[str] = None


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=2000)
    template_slug: Optional[str] = None
    config_overrides: Dict[str, Any] = Field(default_factory=dict)
    create_domain_hostname: Optional[str] = None
    auto_publish: bool = False
    # If true and caller is platform admin — create a fresh company (factory mode)
    create_company: bool = False
    company_name: Optional[str] = None
    company_slug: Optional[str] = None


class PublishProductRequest(BaseModel):
    hostname: Optional[str] = None


REUSE_EXISTING_MESSAGE = (
    "Template already installed. Opening your existing AI workspace."
)


class ProductGenerationResponse(BaseModel):
    id: UUID
    company_id: UUID
    prompt: str
    status: str
    analysis: Dict[str, Any] = Field(default_factory=dict)
    template_id: Optional[UUID] = None
    template_slug: Optional[str] = None
    installation_id: Optional[UUID] = None
    agent_id: Optional[UUID] = None
    knowledge_base_id: Optional[UUID] = None
    api_key_id: Optional[UUID] = None
    api_key_prefix: Optional[str] = None
    api_key: Optional[str] = None  # one-time
    widget_id: Optional[str] = None
    domain_id: Optional[UUID] = None
    product_config: Dict[str, Any] = Field(default_factory=dict)
    preview_url: Optional[str] = None
    widget_snippet: Optional[str] = None
    publish_status: Optional[str] = None
    deployment_checklist: List[Dict[str, Any]] = Field(default_factory=list)
    result: Dict[str, Any] = Field(default_factory=dict)
    failure_reason: Optional[str] = None
    # Idempotent reuse when marketplace template is already installed for the company
    already_installed: bool = False
    reuse_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProductGeneratorOutput(BaseModel):
    """Canonical Step 7 output contract."""

    generation_id: UUID
    preview_url: Optional[str] = None
    publish_status: str
    widget: Optional[Dict[str, Any]] = None
    api_key: Optional[str] = None
    deployment_checklist: List[Dict[str, Any]] = Field(default_factory=list)
    agent_id: Optional[UUID] = None
    template_slug: Optional[str] = None
    installation_id: Optional[UUID] = None
