import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.models.base import Base, TimestampMixin

class EmbeddingsMetadata(Base, TimestampMixin):
    __tablename__ = "agent_kb_embeddings_meta"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    chunk_id = Column(UUID(as_uuid=True), ForeignKey("agent_kb_chunks.id", ondelete="CASCADE"), nullable=False)
    
    model_name = Column(String(100), nullable=False)
    dimensions = Column(Integer, nullable=False)
    status = Column(String(50), default="SUCCESS", nullable=False)

class WebsiteSource(Base, TimestampMixin):
    __tablename__ = "agent_kb_websites"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("agent_kb_documents.id", ondelete="CASCADE"), nullable=False)
    
    url = Column(String(1024), nullable=False)
    crawl_depth = Column(Integer, default=1, nullable=False)
    last_crawled_at = Column(DateTime(timezone=True), nullable=True)
