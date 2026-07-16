import uuid
from sqlalchemy import Column, String, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin

class KnowledgeBase(Base, TimestampMixin):
    __tablename__ = "agent_knowledge_bases"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

class KnowledgeBaseAgent(Base, TimestampMixin):
    __tablename__ = "agent_kb_attachments"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    knowledge_base_id = Column(UUID(as_uuid=True), ForeignKey("agent_knowledge_bases.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False)
