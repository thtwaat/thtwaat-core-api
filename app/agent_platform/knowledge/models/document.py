import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin

class Document(Base, TimestampMixin):
    __tablename__ = "agent_kb_documents"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    knowledge_base_id = Column(UUID(as_uuid=True), ForeignKey("agent_knowledge_bases.id", ondelete="CASCADE"), nullable=True)
    
    name = Column(String(255), nullable=False)
    source_type = Column(String(50), nullable=False) # PDF, DOCX, TXT, MD, URL, FAQ
    version = Column(Integer, default=1, nullable=False)
    status = Column(String(50), default="PENDING", nullable=False) # INDEXED, PENDING, ERROR
    content_metadata = Column(JSONB, default=dict, nullable=False)
