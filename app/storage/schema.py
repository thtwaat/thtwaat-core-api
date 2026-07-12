"""
app/storage/schema.py

Pydantic schemas for the Storage module.
"""

import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

from app.storage.model import StorageProvider


class FileMetadataResponse(BaseModel):
    """Response schema for returning file metadata."""
    id: uuid.UUID
    company_id: Optional[uuid.UUID] = None
    user_id: Optional[uuid.UUID] = None
    
    original_filename: str
    storage_filename: str
    mime_type: str
    extension: str
    size_bytes: int
    
    provider: StorageProvider
    storage_path: str
    
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class FileUploadResponse(BaseModel):
    """Simplified response returned immediately after upload."""
    id: uuid.UUID
    original_filename: str
    size_bytes: int
    mime_type: str
    provider: StorageProvider
    # In a real app, this might be a full URL, but here we just return the path/id.
    url: str
    
    model_config = ConfigDict(from_attributes=True)
