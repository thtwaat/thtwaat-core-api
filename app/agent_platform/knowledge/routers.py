"""
app/agent_platform/knowledge/routers.py
FastAPI router for the Knowledge Base module.
All routes are scoped to the authenticated company (multi-tenant isolation).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID

from app.database.database import get_db
from app.auth.dependencies import get_current_user_and_company
from app.agent_platform.models.agent import AgentConfig
from app.agent_platform.knowledge.schemas import (
    KnowledgeBaseCreate,
    KnowledgeBaseResponse,
    DocumentResponse,
    SearchQuery,
    SearchResponse,
    RAGQueryRequest,
    RAGQueryResponse,
    SourceItem,
)
from app.agent_platform.knowledge.services import KnowledgeService

router = APIRouter(prefix="/v2/knowledge", tags=["Knowledge Base"])


def _require_company_agent(db: Session, agent_id: UUID, company_id: UUID) -> AgentConfig:
    """Ensure the agent belongs to the authenticated company (reject cross-tenant IDs)."""
    agent = (
        db.query(AgentConfig)
        .filter(
            AgentConfig.id == agent_id,
            AgentConfig.company_id == company_id,
            AgentConfig.deleted_at.is_(None),
        )
        .first()
    )
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


# ── Knowledge Base CRUD ───────────────────────────────────────────────────────

@router.post("/bases", response_model=KnowledgeBaseResponse, status_code=201)
def create_knowledge_base(
    kb_in: KnowledgeBaseCreate,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """Create a new knowledge base for the authenticated company."""
    company_id = auth_data.get("company_id")
    return KnowledgeService.create_knowledge_base(db, company_id, kb_in)


@router.get("/bases", response_model=List[KnowledgeBaseResponse])
def list_knowledge_bases(
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """List all knowledge bases for the authenticated company."""
    company_id = auth_data.get("company_id")
    return KnowledgeService.get_knowledge_bases(db, company_id)


@router.get("/bases/{kb_id}", response_model=KnowledgeBaseResponse)
def get_knowledge_base(
    kb_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """Get a single knowledge base (company-scoped)."""
    company_id = auth_data.get("company_id")
    return KnowledgeService.get_knowledge_base(db, kb_id, company_id)


@router.delete("/bases/{kb_id}", status_code=204)
def delete_knowledge_base(
    kb_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """Delete a knowledge base and all its documents/chunks."""
    company_id = auth_data.get("company_id")
    KnowledgeService.delete_knowledge_base(db, kb_id, company_id)


@router.post("/bases/{kb_id}/agents/{agent_id}", status_code=200)
def attach_agent(
    kb_id: UUID,
    agent_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """Attach a knowledge base to an agent (both must belong to the same company)."""
    company_id = auth_data.get("company_id")
    KnowledgeService.get_knowledge_base(db, kb_id, company_id)  # raises 404 if not found
    _require_company_agent(db, agent_id, company_id)
    KnowledgeService.attach_knowledge_base_to_agent(db, kb_id, agent_id)
    return {"message": "Knowledge base attached to agent successfully"}


@router.delete("/bases/{kb_id}/agents/{agent_id}", status_code=200)
def detach_agent(
    kb_id: UUID,
    agent_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """Detach a knowledge base from an agent (both must belong to the same company)."""
    company_id = auth_data.get("company_id")
    KnowledgeService.get_knowledge_base(db, kb_id, company_id)  # raises 404 if not found
    _require_company_agent(db, agent_id, company_id)
    KnowledgeService.detach_knowledge_base_from_agent(db, kb_id, agent_id)
    return {"message": "Knowledge base detached from agent successfully"}


@router.get("/agents/{agent_id}/bases", response_model=List[KnowledgeBaseResponse])
def list_agent_bases(
    agent_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """List knowledge bases attached to an agent (company-scoped)."""
    company_id = auth_data.get("company_id")
    return KnowledgeService.list_agent_knowledge_bases(db, agent_id, company_id)


# ── Document Upload (multipart) ───────────────────────────────────────────────

@router.post("/upload", response_model=DocumentResponse, status_code=201)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="PDF, DOCX, TXT, or MD file"),
    knowledge_base_id: Optional[UUID] = Query(
        default=None,
        description="Optional: attach document to a knowledge base",
    ),
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """
    Upload a document file (PDF, DOCX, TXT, MD).

    - Validates file type and size
    - Saves file to local storage (company-isolated directory)
    - Creates a Document record with status=PENDING
    - Schedules extraction → chunking → embedding as a BackgroundTask
    """
    company_id = auth_data.get("company_id")

    if knowledge_base_id:
        KnowledgeService.get_knowledge_base(db, knowledge_base_id, company_id)

    doc = await KnowledgeService.upload_document(
        db=db,
        company_id=company_id,
        file=file,
        knowledge_base_id=knowledge_base_id,
    )

    # Schedule the full indexing pipeline as a background task
    background_tasks.add_task(
        KnowledgeService.index_document,
        doc_id=doc.id,
        company_id=company_id,
    )

    return doc


# ── Document CRUD ─────────────────────────────────────────────────────────────

@router.get("/documents", response_model=List[DocumentResponse])
def list_documents(
    kb_id: Optional[UUID] = Query(default=None, description="Filter by knowledge base"),
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """List all documents for the authenticated company."""
    company_id = auth_data.get("company_id")
    return KnowledgeService.get_documents(db, company_id, kb_id)


@router.get("/documents/{doc_id}", response_model=DocumentResponse)
def get_document(
    doc_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """Get a single document (company-scoped)."""
    company_id = auth_data.get("company_id")
    return KnowledgeService.get_document(db, doc_id, company_id)


@router.delete("/documents/{doc_id}", status_code=200)
def delete_document(
    doc_id: UUID,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """Delete a document, its chunks, and the physical file."""
    company_id = auth_data.get("company_id")
    KnowledgeService.delete_document(db, doc_id, company_id)
    return {"message": "Document deleted successfully"}


@router.post("/documents/{doc_id}/reindex", status_code=200)
async def reindex_document(
    doc_id: UUID,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """Trigger re-extraction and re-indexing for a document."""
    company_id = auth_data.get("company_id")
    doc = await KnowledgeService.reindex_document(db, doc_id, company_id)

    # Schedule full re-indexing in the background
    background_tasks.add_task(
        KnowledgeService.index_document,
        doc_id=doc.id,
        company_id=company_id,
    )

    return {
        "message": "Re-indexing scheduled",
        "document_id": str(doc.id),
        "status": doc.status,
    }


# ── Semantic Search ───────────────────────────────────────────────────────────

@router.post("/search", response_model=SearchResponse)
def search_knowledge(
    query: SearchQuery,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """
    Semantic similarity search across indexed knowledge base chunks.
    Uses pgvector cosine distance for ranking.
    Returns empty results if no documents are indexed yet.
    """
    company_id = auth_data.get("company_id")
    results = KnowledgeService.search_knowledge_base(
        db=db,
        query=query.query,
        top_k=query.top_k,
        company_id=company_id,
        kb_id=query.knowledge_base_id,
    )
    try:
        from app.usage.dimensions import UsageDimension
        from app.usage.service import UsageService

        UsageService(db).record(
            company_id,
            UsageDimension.KNOWLEDGE_SEARCHES,
            1,
            source="knowledge_search",
        )
    except Exception:
        pass
    return SearchResponse(
        query=query.query,
        results=results,
        total=len(results),
    )


# ── RAG Query (Phase 6) ───────────────────────────────────────────────────────

@router.post("/query", response_model=RAGQueryResponse)
async def rag_query(
    request: RAGQueryRequest,
    db: Session = Depends(get_db),
    auth_data: dict = Depends(get_current_user_and_company),
):
    """
    Full RAG pipeline: retrieve relevant chunks → build context prompt → AI response.

    Flow:
      User Question → Knowledge Search → Relevant Chunks → Prompt Builder → AI Gateway

    The AI Gateway is provider-independent: pass provider + model to control
    which LLM generates the final answer (Gemini, OpenAI, Anthropic, Ollama, OpenRouter).
    """
    from app.agent_platform.knowledge.rag_service import RAGService

    company_id = auth_data.get("company_id")

    result = await RAGService.query(
        db=db,
        question=request.question,
        company_id=company_id,
        kb_id=request.knowledge_base_id,
        agent_id=request.agent_id,
        provider=request.provider,
        model=request.model,
        top_k=request.top_k,
    )

    return RAGQueryResponse(
        question=request.question,
        answer=result["answer"],
        sources=[
            SourceItem(
                chunk_id=s.chunk_id,
                document_id=s.document_id,
                document_name=s.document_name,
                text=s.text,
                score=s.score,
                metadata=s.metadata,
            )
            for s in result["sources"]
        ],
        provider=result["provider"],
        model=result["model"],
    )
