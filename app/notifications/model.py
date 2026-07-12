"""
app/notifications/model.py

SQLAlchemy models for Notifications.
"""
import uuid
import enum
from sqlalchemy import Column, String, Text, Enum as SAEnum, ForeignKey, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin

class NotificationChannel(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    WHATSAPP = "whatsapp"
    PUSH = "push"

class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"

class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True)

    channel = Column(SAEnum(NotificationChannel, name="notification_channel_enum"), nullable=False)
    recipient = Column(String(255), nullable=False)
    subject = Column(String(255), nullable=True)
    body = Column(Text, nullable=False)
    template_name = Column(String(255), nullable=True)
    
    status = Column(SAEnum(NotificationStatus, name="notification_status_enum"), default=NotificationStatus.PENDING, nullable=False)
    provider = Column(String(50), nullable=False) # e.g., 'sendgrid', 'twilio', 'stub'
    
    retry_count = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)
    
    sent_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Notification id={self.id} channel={self.channel} status={self.status}>"
