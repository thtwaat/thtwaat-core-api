import uuid
from sqlalchemy import Column, String, Float, ForeignKey, Text, Integer, Boolean
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin

class AgentConfig(Base, TimestampMixin):
    __tablename__ = "agent_configs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    system_prompt_template = Column(Text, nullable=False)
    default_model_id = Column(UUID(as_uuid=True), ForeignKey("agent_model_configs.id", ondelete="SET NULL"), nullable=True)
    allowed_tools = Column(JSONB, default=list, nullable=False)
    temperature = Column(Float, nullable=False, default=0.7)

    # Sprint 14 Customer AI Platform fields
    status = Column(String(50), default="DRAFT", nullable=False)
    version = Column(Integer, default=1, nullable=False)
    is_template = Column(Boolean, default=False, nullable=False)
    web_config = Column(JSONB, default=dict, nullable=False)
