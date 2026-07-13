"""
app/products/schema.py

Pydantic schemas for Products module.
"""
import uuid
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
from app.products.model import ProductCategory, ProductStatus

class ProductCreate(BaseModel):
    name: str
    slug: Optional[str] = None
    app_id: Optional[uuid.UUID] = None
    category: ProductCategory
    description: Optional[str] = None
    icon: Optional[str] = None
    version: Optional[str] = "1.0.0"
    
    ai_enabled: Optional[bool] = False
    storage_enabled: Optional[bool] = False
    payment_enabled: Optional[bool] = False
    notification_enabled: Optional[bool] = False
    
    settings: Optional[Dict[str, Any]] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    app_id: Optional[uuid.UUID] = None
    category: Optional[ProductCategory] = None
    description: Optional[str] = None
    icon: Optional[str] = None
    version: Optional[str] = None
    status: Optional[ProductStatus] = None
    
    ai_enabled: Optional[bool] = None
    storage_enabled: Optional[bool] = None
    payment_enabled: Optional[bool] = None
    notification_enabled: Optional[bool] = None
    
    settings: Optional[Dict[str, Any]] = None
    metadata_: Optional[Dict[str, Any]] = Field(None, alias="metadata")

class ProductResponse(BaseModel):
    id: uuid.UUID
    company_id: uuid.UUID
    app_id: Optional[uuid.UUID]
    name: str
    slug: str
    category: ProductCategory
    description: Optional[str]
    icon: Optional[str]
    version: str
    status: ProductStatus
    
    ai_enabled: bool
    storage_enabled: bool
    payment_enabled: bool
    notification_enabled: bool
    
    settings: Optional[Dict[str, Any]]
    metadata_: Optional[Dict[str, Any]] = Field(None, serialization_alias="metadata")
    
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True
        populate_by_name = True
