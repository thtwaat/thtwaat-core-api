import uuid
from sqlalchemy import Column, String, Integer, ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.models.base import Base, TimestampMixin

try:
    from pgvector.sqlalchemy import Vector
    _PGVECTOR_AVAILABLE = True
except ImportError:
    # pgvector not installed yet — column will be added by migration
    Vector = None
    _PGVECTOR_AVAILABLE = False


class DocumentChunk(Base, TimestampMixin):
    __tablename__ = "agent_kb_chunks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    document_id = Column(UUID(as_uuid=True), ForeignKey("agent_kb_documents.id", ondelete="CASCADE"), nullable=False)

    chunk_index = Column(Integer, nullable=False)
    text_content = Column(Text, nullable=False)
    metadata_json = Column(JSONB, default=dict, nullable=False)  # E.g., page_number, headers

    # Vector embedding column — added in Sprint 4 migration
    # Type is Vector(768) when pgvector is available, otherwise skipped at model level
    if _PGVECTOR_AVAILABLE and Vector is not None:
        embedding = Column(Vector(768), nullable=True)

