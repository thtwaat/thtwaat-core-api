"""
app/notifications/schema.py

Pydantic schemas for the Notifications module.
"""
import uuid
from typing import Optional, Dict, Any, List
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.notifications.model import NotificationChannel, NotificationStatus


class SendNotificationRequest(BaseModel):
    channel: NotificationChannel
    recipient: str = Field(..., max_length=255)
    subject: Optional[str] = Field(None, max_length=255)
    body: str
    template_name: Optional[str] = Field(None, max_length=255)
    template_data: Optional[Dict[str, Any]] = None


class MarkReadRequest(BaseModel):
    notification_ids: Optional[List[uuid.UUID]] = None  # If None, marks all as read


class NotificationResponse(BaseModel):
    id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    actor_id: Optional[uuid.UUID] = None

    channel: NotificationChannel
    recipient: str
    subject: Optional[str]
    body: str
    template_name: Optional[str]

    event_type: Optional[str]
    extra_data: Optional[Dict[str, Any]]
    read_at: Optional[datetime]

    status: NotificationStatus
    provider: str
    retry_count: int
    error_message: Optional[str]

    sent_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InboxResponse(BaseModel):
    """Summary response for inbox listing."""
    id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    event_type: Optional[str]
    subject: Optional[str]
    body: str
    extra_data: Optional[Dict[str, Any]]
    read_at: Optional[datetime]
    is_read: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @classmethod
    def from_notification(cls, n) -> "InboxResponse":
        return cls(
            id=n.id,
            company_id=n.company_id,
            user_id=n.user_id,
            event_type=n.event_type,
            subject=n.subject,
            body=n.body,
            extra_data=n.extra_data,
            read_at=n.read_at,
            is_read=n.read_at is not None,
            created_at=n.created_at,
        )
