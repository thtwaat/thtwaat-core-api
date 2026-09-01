from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Any, Optional
from uuid import UUID
from datetime import datetime

class UnifiedChatRequest(BaseModel):
    company_id: str
    agent_id: Optional[str] = None
    provider: str
    model: str
    messages: List[Dict[str, Any]] = Field(..., description="List of messages with 'role' and 'content'")
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    tools: Optional[List[Dict[str, Any]]] = None

class UnifiedChatResponse(BaseModel):
    content: str
    provider: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    latency: float = 0.0
    finish_reason: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None

class AgentCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    description: Optional[str] = None
    system_prompt_template: str
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float = 0.7
    is_template: bool = False
    allowed_tools: List[str] = []
    web_config: Dict[str, Any] = {}

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt_template: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: Optional[float] = None
    allowed_tools: Optional[List[str]] = None
    web_config: Optional[Dict[str, Any]] = None

class AgentResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    slug: Optional[str] = None
    description: Optional[str]
    system_prompt_template: str
    provider: Optional[str] = None
    model: Optional[str] = None
    temperature: float
    status: str
    version: int
    is_template: bool
    allowed_tools: List[str] = []
    web_config: Dict[str, Any]
    published_at: Optional[datetime] = None
    widget_id: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AgentDeleteRequest(BaseModel):
    keep_conversations: bool = True
    keep_knowledge: bool = True
    reason: Optional[str] = None
    confirm_unpublish: bool = False


class AgentDeleteImpact(BaseModel):
    agent_id: str
    name: str
    published: bool
    status: str
    widget: bool
    widget_id: Optional[str] = None
    api_keys: int
    playground: bool
    draft_prompts: int
    scheduled_jobs: int
    conversations: int
    knowledge_attachments: int
    retention_days: int


class AgentDeleteResponse(BaseModel):
    id: UUID
    status: str
    deleted_at: datetime
    retention_days: int
    message: str

    model_config = ConfigDict(from_attributes=True)


class AgentRestoreRequest(BaseModel):
    reason: Optional[str] = None


class AgentRestoreResponse(BaseModel):
    id: UUID
    status: str
    company_id: UUID
    message: str

    model_config = ConfigDict(from_attributes=True)


class ApiKeyResponse(BaseModel):
    id: UUID
    key_hash: str
    name: Optional[str]
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class AgentCapabilities(BaseModel):
    """Documents the shape of ``AgentConfig.web_config['capabilities']``.

    web_config itself stays an untyped dict on the wire (changing that would be
    a breaking API change); this model exists for internal validation/reference
    and as the single place new capabilities (voice, calling, image_generation)
    get documented.
    """

    memory: bool = True
    handoff: bool = True
    tools: bool = False
    lead_capture: bool = True
    multilingual: bool = True
    vision: bool = False
    voice: bool = False
    calling: bool = False
    image_generation: bool = False


class AgentVoiceConfig(BaseModel):
    """Documents the shape of ``AgentConfig.web_config['voice']``."""

    provider: str = "openai"
    voice_id: str = "alloy"
    language: Optional[str] = None
    speed: float = 1.0


class AgentCallingConfig(BaseModel):
    """Documents the shape of ``AgentConfig.web_config['calling']``."""

    provider: str = "twilio"
    phone_number: Optional[str] = None
    voice_id: str = "alloy"
    language: Optional[str] = None
    greeting: str = "Hello! How can I help you today?"
    human_handoff: bool = False
    human_handoff_number: Optional[str] = None


class AgentImageGenerationConfig(BaseModel):
    """Documents the shape of ``AgentConfig.web_config['image_generation']``."""

    provider: str = "openai"
    model: str = "dall-e-3"
    size: str = "1024x1024"
    quality: str = "standard"


class AgentChatRequest(BaseModel):
    message: str
    conversation_id: Optional[UUID] = None
    images: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description=(
            'Optional image content blocks, e.g. '
            '[{"type": "image_url", "image_url": {"url": "https://..."}}]. '
            "Requires the agent's vision capability and a vision-capable model."
        ),
    )


class AgentChatUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    provider: Optional[str] = None
    model: Optional[str] = None


class AgentChatResponse(BaseModel):
    message: str
    conversation_id: UUID
    usage: AgentChatUsage


class AgentToolInfo(BaseModel):
    name: str
    description: str


class AgentVoiceResponse(BaseModel):
    """Response for a single voice turn (dashboard push-to-talk or public widget mic).

    Audio is returned base64-encoded JSON (not a binary body) to stay consistent
    with the rest of the Agent Platform's JSON API surface.
    """

    conversation_id: UUID
    transcript: str
    reply: str
    audio_base64: str
    audio_mime_type: str
    usage: AgentChatUsage
    status: Optional[str] = None
    handoff: bool = False


class GeneratedImage(BaseModel):
    """A single generated image. ``data_base64`` always carries the image so
    the caller never needs a follow-up authenticated fetch; ``url`` (when
    present) is a durable, dashboard-authenticated copy via StorageService."""

    data_base64: str
    mime_type: str = "image/png"
    url: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    revised_prompt: Optional[str] = None


class AgentImageRequest(BaseModel):
    prompt: str
    conversation_id: Optional[UUID] = None


class AgentImageResponse(BaseModel):
    conversation_id: UUID
    images: List[GeneratedImage]
    usage: AgentChatUsage
    status: Optional[str] = None
