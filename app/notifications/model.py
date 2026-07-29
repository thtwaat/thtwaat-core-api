"""
app/notifications/model.py

SQLAlchemy models for Notifications.
Supports both external channels (email, sms, etc.) and in-app notifications.
"""
import uuid
import enum
from sqlalchemy import Column, String, Text, Enum as SAEnum, ForeignKey, DateTime, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin


class NotificationChannel(str, enum.Enum):
    EMAIL    = "email"
    SMS      = "sms"
    WHATSAPP = "whatsapp"
    PUSH     = "push"
    IN_APP   = "in_app"   # Phase 4 — in-app / inbox notifications


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT    = "sent"
    FAILED  = "failed"
    READ    = "read"  # Only relevant for IN_APP


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)

    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=True)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),    index=True, nullable=True)
    actor_id   = Column(UUID(as_uuid=True), nullable=True)  # Who triggered the event

    channel        = Column(SAEnum(NotificationChannel, name="notification_channel_enum"), nullable=False)
    recipient      = Column(String(255), nullable=False)
    subject        = Column(String(255), nullable=True)
    body           = Column(Text, nullable=False)
    template_name  = Column(String(255), nullable=True)

    # Event bus fields (Phase 4/5)
    event_type  = Column(String(100), nullable=True, index=True)   # e.g. "payment.success"
    extra_data  = Column(JSONB, nullable=True)                     # Contextual payload for the event
    read_at     = Column(DateTime(timezone=True), nullable=True)   # NULL = unread (IN_APP only)

    status   = Column(SAEnum(NotificationStatus, name="notification_status_enum"), default=NotificationStatus.PENDING, nullable=False)
    provider = Column(String(50), nullable=False)  # e.g. 'sendgrid', 'twilio', 'in_app'

    retry_count   = Column(Integer, default=0, nullable=False)
    error_message = Column(Text, nullable=True)

    sent_at    = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Notification id={self.id} channel={self.channel} status={self.status}>"
