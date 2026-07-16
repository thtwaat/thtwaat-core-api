import uuid
from sqlalchemy import Column, Float, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, TimestampMixin

class CompanyQuota(Base, TimestampMixin):
    """Tracks and enforces limits for a company's agent platform usage."""
    __tablename__ = "agent_company_quotas"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True, nullable=False)
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    monthly_spend_limit = Column(Float, nullable=False, default=50.0) # $50 default limit
    current_spend = Column(Float, nullable=False, default=0.0)
    
    monthly_token_limit = Column(Integer, nullable=False, default=100000)
    current_tokens = Column(Integer, nullable=False, default=0)
