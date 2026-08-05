from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Dict, List, Optional
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
    channel: Optional[str] = "dashboard"


class ConversationUpdate(BaseModel):
    """Assignment / handoff / read updates for Unified Inbox."""

    title: Optional[str] = None
    status: Optional[str] = None
    assigned_to_user_id: Optional[UUID] = None
    clear_assignee: bool = False
    mark_read: bool = False


class ConversationResponse(BaseModel):
    id: UUID
    company_id: UUID
    agent_id: UUID
    title: Optional[str] = None
    channel: str = "dashboard"
    status: str = "open"
    assigned_to_user_id: Optional[UUID] = None
    last_read_at: Optional[datetime] = None
    extra_metadata: Dict[str, Any] = Field(default_factory=dict)
    message_count: int = 0
    last_message_preview: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConversationDetailResponse(ConversationResponse):
    messages: List[MessageResponse] = []


class MessageCreate(BaseModel):
    content: str
    as_human: bool = False
    request_handoff: bool = False
