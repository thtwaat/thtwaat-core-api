from pydantic import BaseModel, Field, UUID4, ConfigDict
from typing import Optional, List, Dict, Any
from datetime import datetime
from app.features.ai_platform.database.models import AiModelType, AiConversationStatus, AiMessageRole

class TimestampResponse(BaseModel):
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# Provider Schemas
class AiProviderBase(BaseModel):
    name: str = Field(..., max_length=100)
    base_url: Optional[str] = Field(None, max_length=500)
    is_active: bool = True

class AiProviderCreate(AiProviderBase):
    api_key: str = Field(...)

class AiProviderUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    base_url: Optional[str] = Field(None, max_length=500)
    api_key: Optional[str] = None
    is_active: Optional[bool] = None

class AiProviderResponse(AiProviderBase, TimestampResponse):
    id: UUID4
    company_id: UUID4

# Model Schemas
class AiModelBase(BaseModel):
    name: str = Field(..., max_length=100)
    type: AiModelType = AiModelType.CHAT
    cost_per_1k_input: float = 0.0
    cost_per_1k_output: float = 0.0

class AiModelCreate(AiModelBase):
    provider_id: UUID4

class AiModelUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    type: Optional[AiModelType] = None
    cost_per_1k_input: Optional[float] = None
    cost_per_1k_output: Optional[float] = None

class AiModelResponse(AiModelBase, TimestampResponse):
    id: UUID4
    provider_id: UUID4
    company_id: UUID4

# Prompt Template Schemas
class AiPromptTemplateBase(BaseModel):
    name: str = Field(..., max_length=100)
    template_text: str
    variables_json: List[str] = Field(default_factory=list)

class AiPromptTemplateCreate(AiPromptTemplateBase):
    pass

class AiPromptTemplateUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    template_text: Optional[str] = None
    variables_json: Optional[List[str]] = None

class AiPromptTemplateResponse(AiPromptTemplateBase, TimestampResponse):
    id: UUID4
    company_id: UUID4

# Tool Schemas
class AiToolBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: str
    json_schema: Dict[str, Any]
    is_active: bool = True

class AiToolCreate(AiToolBase):
    pass

class AiToolUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    json_schema: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

class AiToolResponse(AiToolBase, TimestampResponse):
    id: UUID4
    company_id: UUID4

# Agent Schemas
class AiAgentBase(BaseModel):
    name: str = Field(..., max_length=100)
    description: Optional[str] = None
    configuration_json: Dict[str, Any] = Field(default_factory=dict)

class AiAgentCreate(AiAgentBase):
    system_prompt_id: Optional[UUID4] = None
    model_id: Optional[UUID4] = None
    tool_ids: List[UUID4] = Field(default_factory=list)

class AiAgentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = None
    system_prompt_id: Optional[UUID4] = None
    model_id: Optional[UUID4] = None
    configuration_json: Optional[Dict[str, Any]] = None
    tool_ids: Optional[List[UUID4]] = None

class AiAgentResponse(AiAgentBase, TimestampResponse):
    id: UUID4
    company_id: UUID4
    system_prompt_id: Optional[UUID4] = None
    model_id: Optional[UUID4] = None
    # We could also include nested tools/prompts depending on requirements

# Conversation Schemas
class AiConversationBase(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    status: AiConversationStatus = AiConversationStatus.ACTIVE

class AiConversationCreate(AiConversationBase):
    agent_id: UUID4

class AiConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    status: Optional[AiConversationStatus] = None

class AiConversationResponse(AiConversationBase, TimestampResponse):
    id: UUID4
    company_id: UUID4
    agent_id: UUID4

# Usage Tracking Schemas
class AiUsageBase(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0

class AiUsageCreate(AiUsageBase):
    conversation_id: UUID4
    model_id: Optional[UUID4] = None

class AiUsageResponse(AiUsageBase, TimestampResponse):
    id: UUID4
    company_id: UUID4
    conversation_id: UUID4
    model_id: Optional[UUID4] = None
