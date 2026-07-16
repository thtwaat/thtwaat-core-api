import uuid
from sqlalchemy import Column, String, ForeignKey, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin

class AgentApiKey(Base, TimestampMixin):
    """Stores API keys generated for specific agents."""
    __tablename__ = "agent_api_keys"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id", ondelete="CASCADE"), nullable=False)
    
    key_hash = Column(String(255), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=True) # E.g., "Production Website Key"
    is_active = Column(Boolean, default=True, nullable=False)
