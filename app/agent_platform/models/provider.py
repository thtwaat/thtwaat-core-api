import uuid
from sqlalchemy import Column, String, Float, Boolean, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin

class ProviderConfig(Base, TimestampMixin):
    __tablename__ = "agent_provider_configs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    provider_name = Column(String(50), nullable=False)
    api_key_secret = Column(String(255), nullable=False)
    base_url = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    models = relationship("ModelConfig", back_populates="provider", cascade="all, delete-orphan")

class ModelConfig(Base, TimestampMixin):
    __tablename__ = "agent_model_configs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    provider_id = Column(UUID(as_uuid=True), ForeignKey("agent_provider_configs.id", ondelete="CASCADE"), nullable=False)
    model_name = Column(String(100), nullable=False)
    cost_per_1k_prompt = Column(Float, nullable=False, default=0.0)
    cost_per_1k_completion = Column(Float, nullable=False, default=0.0)
    context_window = Column(Integer, nullable=False, default=8192)

    provider = relationship("ProviderConfig", back_populates="models")
