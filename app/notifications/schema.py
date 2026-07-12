"""
app/notifications/schema.py

Pydantic schemas for the Notifications module.
"""
import uuid
from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.notifications.model import NotificationChannel, NotificationStatus


class SendNotificationRequest(BaseModel):
    channel: NotificationChannel
    recipient: str = Field(..., max_length=255)
    subject: Optional[str] = Field(None, max_length=255)
    body: str
    template_name: Optional[str] = Field(None, max_length=255)
    template_data: Optional[Dict[str, Any]] = None # Basic template support


class NotificationResponse(BaseModel):
    id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    
    channel: NotificationChannel
    recipient: str
    subject: Optional[str]
    body: str
    template_name: Optional[str]
    
    status: NotificationStatus
    provider: str
    retry_count: int
    error_message: Optional[str]
    
    sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)
