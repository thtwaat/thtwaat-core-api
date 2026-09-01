import uuid
from sqlalchemy import Column, String, ForeignKey, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin


# Channels unified in one inbox. "voice" = mic/push-to-talk turns (widget or
# dashboard); "call" = a telephony call session (see app/agent_platform/telephony);
# "image" = a text-prompt image-generation turn (see app/agent_platform/image_generation).
INBOX_CHANNELS = frozenset({"widget", "dashboard", "api", "voice", "call", "image"})
# Handoff-ready statuses — human reply path can land later without schema churn
INBOX_STATUSES = frozenset({"open", "pending_human", "human", "closed"})


class Conversation(Base, TimestampMixin):
    __tablename__ = "agent_conversations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=True)
    channel = Column(String(32), nullable=False, default="dashboard", server_default="dashboard", index=True)
    status = Column(String(32), nullable=False, default="open", server_default="open", index=True)
    assigned_to_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    last_read_at = Column(DateTime(timezone=True), nullable=True)
    extra_metadata = Column(JSONB, nullable=False, default=dict, server_default="{}")

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base, TimestampMixin):
    __tablename__ = "agent_messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False)  # user, assistant, tool, system
    content = Column(Text, nullable=True)
    tool_calls = Column(JSONB, nullable=True)

    conversation = relationship("Conversation", back_populates="messages")
