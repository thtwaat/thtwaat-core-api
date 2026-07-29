"""Pydantic schemas for Agent Publish Service."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WidgetConfig(BaseModel):
    theme: str = "light"
    primary_color: str = "#111827"
    welcome_message: str = "Hi! How can I help you today?"
    logo: Optional[str] = None
    avatar: Optional[str] = None
    position: str = "bottom-right"
    border_radius: str = "16px"
    font_family: str = "Inter, system-ui, sans-serif"
    suggested_prompts: list[str] = Field(
        default_factory=lambda: ["Pricing?", "Book appointment", "Contact support"]
    )
    agent_name: Optional[str] = None


class WidgetConfigUpdate(BaseModel):
    theme: Optional[str] = None
    primary_color: Optional[str] = None
    welcome_message: Optional[str] = None
    logo: Optional[str] = None
    avatar: Optional[str] = None
    position: Optional[str] = None
    border_radius: Optional[str] = None
    font_family: Optional[str] = None
    suggested_prompts: Optional[list[str]] = None
    agent_name: Optional[str] = None


class EmbedSnippetResponse(BaseModel):
    """Dashboard-ready copy payloads for embed."""

    agent_id: UUID
    widget_id: str
    status: str
    script: str
    iframe: str
    preview_url: str
    config: WidgetConfig



class PublishResponse(BaseModel):
    status: str
    agent_id: UUID
    api_key: Optional[str] = None
    widget_id: str
    public_chat_url: str
    embed_script: str
    iframe_url: str
    published_at: Optional[datetime] = None


class UnpublishResponse(BaseModel):
    status: str
    agent_id: UUID


class AgentApiKeyCreate(BaseModel):
    name: str = "Default Key"
    expires_at: Optional[datetime] = None


class AgentApiKeyCreatedResponse(BaseModel):
    id: UUID
    name: Optional[str]
    key_prefix: Optional[str]
    api_key: str = Field(..., description="Raw key — shown only once")
    expires_at: Optional[datetime] = None
    message: str = "Save this key, it will not be shown again."


class AgentApiKeyListItem(BaseModel):
    id: UUID
    name: Optional[str]
    key_prefix: Optional[str]
    is_active: bool
    last_used_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentApiKeyRotateResponse(BaseModel):
    id: UUID
    name: Optional[str]
    key_prefix: Optional[str]
    api_key: str
    message: str = "Previous key revoked. Save the new key — it will not be shown again."


class WidgetConfigResponse(BaseModel):
    agent_id: UUID
    widget_id: str
    status: str
    config: WidgetConfig
    public_chat_url: str
    embed_script: str
    iframe_url: str


class PublicChatRequest(BaseModel):
    """Simplified public chat body for websites / apps / SaaS embeds."""

    api_key: Optional[str] = Field(
        default=None,
        description="Optional if Authorization: Bearer tht_live_... is set",
    )
    message: str
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class PublicChatUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    provider: Optional[str] = None
    model: Optional[str] = None


class PublicChatResponse(BaseModel):
    reply: str
    conversation_id: str
    usage: PublicChatUsage
