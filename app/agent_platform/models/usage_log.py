import uuid
from sqlalchemy import Column, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin

class UsageLog(Base, TimestampMixin):
    __tablename__ = "agent_usage_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agent_configs.id", ondelete="SET NULL"), nullable=True)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("agent_provider_configs.id", ondelete="SET NULL"), nullable=True)
    model_id = Column(UUID(as_uuid=True), ForeignKey("agent_model_configs.id", ondelete="SET NULL"), nullable=True)
    
    prompt_tokens = Column(Integer, nullable=False, default=0)
    completion_tokens = Column(Integer, nullable=False, default=0)
    total_cost = Column(Float, nullable=False, default=0.0)
