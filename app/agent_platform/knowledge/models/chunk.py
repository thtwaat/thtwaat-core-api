import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin

class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "agent_kb_chunks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("agent_kb_documents.id", ondelete="CASCADE"), nullable=False)
    
    chunk_index = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)
    metadata_json = Column(JSONB, default=dict, nullable=False) # E.g., page_number, headers
