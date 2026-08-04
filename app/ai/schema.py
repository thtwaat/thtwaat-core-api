"""
app/ai/schema.py

Pydantic schemas for AI Gateway validation.
"""
import uuid
from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, ConfigDict
from datetime import datetime
from app.ai.model import AIRequestStatus

# Requests
class ChatMessage(BaseModel):
    role: str
    content: Union[str, List[Dict[str, Any]]]
    name: Optional[str] = None
    tool_call_id: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None


class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    provider: Optional[str] = None
    model: str
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000
    conversation_id: Optional[str] = None
    app_id: Optional[uuid.UUID] = None
    tools: Optional[List[Dict[str, Any]]] = None
    tool_choice: Optional[Union[str, Dict[str, Any]]] = None
    rag_query: Optional[str] = None
    knowledge_base_id: Optional[uuid.UUID] = None
    enable_fallback: bool = True

class GenerateRequest(BaseModel):
    prompt: str
    provider: Optional[str] = None
    model: str
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = 1000
    app_id: Optional[uuid.UUID] = None

# Responses
class AIResponseBase(BaseModel):
    content: str
    input_tokens: int
    output_tokens: int
    model_used: str
    estimated_cost: float
    currency: str

class ChatResponse(AIResponseBase):
    conversation_id: Optional[str] = None

class GenerateResponse(AIResponseBase):
    pass

class AIHistoryResponse(BaseModel):
    id: uuid.UUID
    provider: str
    model: str
    prompt: Any
    response: Any
    tokens_input: int
    tokens_output: int
    latency: float
    estimated_cost: float
    currency: str
    status: AIRequestStatus
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
