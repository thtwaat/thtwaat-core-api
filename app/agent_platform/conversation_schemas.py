from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any, Dict
from uuid import UUID
from datetime import datetime

class MessageResponse(BaseModel):
    id: UUID
    conversation_id: UUID
    role: str
    content: Optional[str] = None
    created_at: datetime
    
    model_config = ConfigDict(from_attributes=True)

class ConversationCreate(BaseModel):
    agent_id: UUID
    title: Optional[str] = "New Conversation"

class ConversationResponse(BaseModel):
    id: UUID
    company_id: UUID
    agent_id: UUID
    title: Optional[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse] = []

class MessageCreate(BaseModel):
    content: str
