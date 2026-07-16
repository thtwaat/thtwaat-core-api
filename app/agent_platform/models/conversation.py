import uuid
from sqlalchemy import Column, String, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin

class Conversation(Base, TimestampMixin):
    __tablename__ = "agent_conversations"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(255), nullable=True)

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")

class Message(Base, TimestampMixin):
    __tablename__ = "agent_messages"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("agent_conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(String(50), nullable=False) # user, assistant, tool, system
    content = Column(Text, nullable=True)
    tool_calls = Column(JSONB, nullable=True)

    conversation = relationship("Conversation", back_populates="messages")
