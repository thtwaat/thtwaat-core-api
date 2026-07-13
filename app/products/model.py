"""
app/products/model.py

Database models for the Products module.
"""
import uuid
import enum
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.models.base import Base

class ProductCategory(str, enum.Enum):
    WEBSITE = "Website"
    MOBILE_APP = "Mobile App"
    AI_AGENT = "AI Agent"
    CRM = "CRM"
    POS = "POS"
    IDE = "IDE"
    DASHBOARD = "Dashboard"
    INTERNAL_TOOL = "Internal Tool"

class ProductStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"

class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    
    company_id = Column(UUID(as_uuid=True), ForeignKey("companies.id"), nullable=False, index=True)
    app_id = Column(UUID(as_uuid=True), ForeignKey("apps.id"), nullable=True, index=True)
    
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True, index=True)
    category = Column(SAEnum(ProductCategory, name="product_category_enum"), nullable=False)
    description = Column(Text, nullable=True)
    icon = Column(String, nullable=True)
    version = Column(String, default="1.0.0")
    
    status = Column(SAEnum(ProductStatus, name="product_status_enum"), default=ProductStatus.ACTIVE, nullable=False)
    
    # Feature Flags
    ai_enabled = Column(Boolean, default=False)
    storage_enabled = Column(Boolean, default=False)
    payment_enabled = Column(Boolean, default=False)
    notification_enabled = Column(Boolean, default=False)
    
    settings = Column(JSONB, nullable=True)
    metadata_ = Column(JSONB, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
