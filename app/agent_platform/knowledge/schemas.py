from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None

class KnowledgeBaseResponse(KnowledgeBaseCreate):
    id: UUID
    company_id: UUID
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class DocumentCreate(BaseModel):
    name: str
    source_type: str
    knowledge_base_id: Optional[UUID] = None
    content_metadata: Optional[Dict[str, Any]] = {}

class DocumentResponse(DocumentCreate):
    id: UUID
    company_id: UUID
    version: int
    status: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

class SearchQuery(BaseModel):
    query: str
    top_k: int = 5
    knowledge_base_id: Optional[UUID] = None
