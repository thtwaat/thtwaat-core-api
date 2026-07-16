"""
app/ai/model.py

Database models for the AI Gateway.
"""
import uuid
import enum
from sqlalchemy import Column, String, Text, Integer, Float, DateTime, ForeignKey, Enum as SAEnum, JSON
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.models.base import Base

class AIRequestStatus(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class AIRequest(Base):
    __tablename__ = "ai_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id", ondelete="SET NULL"), nullable=True, index=True)
    
    provider = Column(String, nullable=False, index=True)
    model = Column(String, nullable=False)
    
    prompt = Column(JSONB, nullable=False) # Can be string or list of messages
    response = Column(JSONB, nullable=True)
    
    # Cost Tracking
    tokens_input = Column(Integer, default=0)
    tokens_output = Column(Integer, default=0)
    latency = Column(Float, default=0.0)
    estimated_cost = Column(Float, default=0.0)
    currency = Column(String, default="USD")
    
    status = Column(SAEnum(AIRequestStatus, name="ai_request_status_enum"), default=AIRequestStatus.SUCCESS, nullable=False)
    
    # Extensible schema for future features (conversation_id, temperature, etc)
    request_metadata = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True) # Soft delete for history
