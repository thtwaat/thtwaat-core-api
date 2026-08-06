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

class AgentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    system_prompt_template: str
    temperature: float = 0.7
    is_template: bool = False
    web_config: Dict[str, Any] = {}

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    system_prompt_template: Optional[str] = None
    temperature: Optional[float] = None
    web_config: Optional[Dict[str, Any]] = None

class AgentResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    description: Optional[str]
    system_prompt_template: str
    temperature: float
    status: str
    version: int
    is_template: bool
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
