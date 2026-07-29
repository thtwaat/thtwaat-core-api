"""
app/agent_platform/knowledge/schemas.py
Pydantic schemas for the Knowledge Base module.
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime


# ── Knowledge Base ────────────────────────────────────────────────────────────

class KnowledgeBaseCreate(BaseModel):
    name: str
    description: Optional[str] = None


class KnowledgeBaseResponse(BaseModel):
    id: UUID
    company_id: UUID
    name: str
    description: Optional[str]
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Document (JSON body) ──────────────────────────────────────────────────────

class DocumentCreate(BaseModel):
    """Used when registering a document via JSON (no file)."""
    name: str
    source_type: str  # PDF, DOCX, TXT, MD, URL, FAQ
    knowledge_base_id: Optional[UUID] = None
    content_metadata: Optional[Dict[str, Any]] = {}


class DocumentResponse(BaseModel):
    id: UUID
    company_id: UUID
    knowledge_base_id: Optional[UUID]
    name: str
    source_type: str
    version: int
    status: str
    content_metadata: Dict[str, Any]
    file_path: Optional[str] = None
    file_size_bytes: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


# ── Chunk ─────────────────────────────────────────────────────────────────────

class ChunkResponse(BaseModel):
    id: UUID
    document_id: UUID
    chunk_index: int
    text_content: str
    metadata_json: Dict[str, Any]
    model_config = ConfigDict(from_attributes=True)


# ── Search ────────────────────────────────────────────────────────────────────

class SearchQuery(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    knowledge_base_id: Optional[UUID] = None


class SearchResult(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    text: str
    score: float
    metadata: Dict[str, Any] = {}


class SearchResponse(BaseModel):
    query: str
    results: List[SearchResult]
    total: int


# ── RAG Query (Phase 6) ───────────────────────────────────────────────────────

class RAGQueryRequest(BaseModel):
    question: str = Field(..., min_length=3, description="The user's natural-language question")
    knowledge_base_id: Optional[UUID] = Field(
        default=None,
        description="Restrict retrieval to a single knowledge base (optional)",
    )
    agent_id: Optional[UUID] = Field(
        default=None,
        description="Agent to attribute this request to (for usage logging)",
    )
    provider: str = Field(
        default="gemini",
        description="LLM provider: gemini | openai | anthropic | ollama | openrouter",
    )
    model: str = Field(
        default="gemini-2.0-flash",
        description="Model name for generation",
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Number of chunks to retrieve")


class SourceItem(BaseModel):
    chunk_id: str
    document_id: str
    document_name: str
    text: str
    score: float
    metadata: Dict[str, Any] = {}


class RAGQueryResponse(BaseModel):
    question: str
    answer: str
    sources: List[SourceItem]
    provider: str
    model: str
