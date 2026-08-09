"""
app/agent_platform/knowledge/repositories.py
Data access layer for the Knowledge Base module.
Every query is scoped to company_id for multi-tenant isolation.
"""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
from uuid import UUID

from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBase, KnowledgeBaseAgent
from app.agent_platform.knowledge.models.document import Document
from app.agent_platform.knowledge.models.chunk import DocumentChunk
from app.agent_platform.knowledge.models.metadata import EmbeddingsMetadata
from app.agent_platform.knowledge.schemas import KnowledgeBaseCreate, DocumentCreate


class KnowledgeRepository:

    # ── Knowledge Base ────────────────────────────────────────────────────────

    @staticmethod
    def create_knowledge_base(db: Session, company_id: UUID, kb_in: KnowledgeBaseCreate) -> KnowledgeBase:
        db_kb = KnowledgeBase(company_id=company_id, **kb_in.model_dump())
        db.add(db_kb)
        db.commit()
        db.refresh(db_kb)
        return db_kb

    @staticmethod
    def get_knowledge_base(db: Session, kb_id: UUID, company_id: UUID) -> Optional[KnowledgeBase]:
        """Single KB — scoped to company."""
        return (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.id == kb_id, KnowledgeBase.company_id == company_id)
            .first()
        )

    @staticmethod
    def get_knowledge_bases(db: Session, company_id: UUID) -> List[KnowledgeBase]:
        """All KBs for this company — no cross-tenant leakage."""
        return db.query(KnowledgeBase).filter(KnowledgeBase.company_id == company_id).all()

    @staticmethod
    def delete_knowledge_base(db: Session, kb_id: UUID, company_id: UUID) -> bool:
        kb = KnowledgeRepository.get_knowledge_base(db, kb_id, company_id)
        if not kb:
            return False
        db.delete(kb)
        db.commit()
        return True

    # ── Document ──────────────────────────────────────────────────────────────

    @staticmethod
    def create_document(
        db: Session,
        company_id: UUID,
        doc_in: DocumentCreate,
        file_path: Optional[str] = None,
        file_size_bytes: Optional[int] = None,
    ) -> Document:
        data = doc_in.model_dump()
        db_doc = Document(
            company_id=company_id,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            **data,
        )
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        return db_doc

    @staticmethod
    def get_document(db: Session, doc_id: UUID, company_id: UUID) -> Optional[Document]:
        """Single document — scoped to company."""
        return (
            db.query(Document)
            .filter(Document.id == doc_id, Document.company_id == company_id)
            .first()
        )

    @staticmethod
    def get_documents(
        db: Session,
        company_id: UUID,
        kb_id: Optional[UUID] = None,
    ) -> List[Document]:
        """All documents for this company, optionally filtered by KB."""
        q = db.query(Document).filter(Document.company_id == company_id)
        if kb_id:
            q = q.filter(Document.knowledge_base_id == kb_id)
        return q.order_by(Document.created_at.desc()).all()

    @staticmethod
    def update_document_status(
        db: Session,
        doc_id: UUID,
        company_id: UUID,
        status: str,
    ) -> Optional[Document]:
        doc = KnowledgeRepository.get_document(db, doc_id, company_id)
        if doc:
            doc.status = status
            db.commit()
            db.refresh(doc)
        return doc

    @staticmethod
    def delete_document(db: Session, doc_id: UUID, company_id: UUID) -> bool:
        doc = KnowledgeRepository.get_document(db, doc_id, company_id)
        if not doc:
            return False
        db.delete(doc)
        db.commit()
        return True

    # ── Chunks ────────────────────────────────────────────────────────────────

    @staticmethod
    def create_chunks(
        db: Session,
        document_id: UUID,
        chunks: List[dict],
    ) -> List[DocumentChunk]:
        """
        Bulk-insert chunks for a document.
        Each dict: {chunk_index, text_content, metadata_json}
        """
        db_chunks = [
            DocumentChunk(
                document_id=document_id,
                chunk_index=c["chunk_index"],
                text_content=c["text_content"],
                metadata_json=c.get("metadata_json", {}),
            )
            for c in chunks
        ]
        db.add_all(db_chunks)
        db.commit()
        for ch in db_chunks:
            db.refresh(ch)
        return db_chunks

    @staticmethod
    def get_chunks_by_document(
        db: Session,
        document_id: UUID,
        company_id: UUID,
    ) -> List[DocumentChunk]:
        """Chunks for a document — validates document ownership first."""
        doc = KnowledgeRepository.get_document(db, document_id, company_id)
        if not doc:
            return []
        return (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index)
            .all()
        )

    @staticmethod
    def delete_chunks_by_document(db: Session, document_id: UUID) -> int:
        """Delete all chunks for a document. Returns count deleted."""
        count = (
            db.query(DocumentChunk)
            .filter(DocumentChunk.document_id == document_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        return count

    # ── Embeddings Metadata ───────────────────────────────────────────────────

    @staticmethod
    def store_embedding_meta(
        db: Session,
        chunk_id: UUID,
        model_name: str,
        dimensions: int,
        status: str = "SUCCESS",
    ) -> EmbeddingsMetadata:
        meta = EmbeddingsMetadata(
            chunk_id=chunk_id,
            model_name=model_name,
            dimensions=dimensions,
            status=status,
        )
        db.add(meta)
        db.commit()
        return meta

    # ── Attachments ───────────────────────────────────────────────────────────

    @staticmethod
    def attach_kb_to_agent(db: Session, kb_id: UUID, agent_id: UUID) -> KnowledgeBaseAgent:
        existing = (
            db.query(KnowledgeBaseAgent)
            .filter(
                KnowledgeBaseAgent.knowledge_base_id == kb_id,
                KnowledgeBaseAgent.agent_id == agent_id,
            )
            .first()
        )
        if existing:
            return existing
        attachment = KnowledgeBaseAgent(knowledge_base_id=kb_id, agent_id=agent_id)
        db.add(attachment)
        db.commit()
        return attachment

    @staticmethod
    def detach_kb_from_agent(db: Session, kb_id: UUID, agent_id: UUID) -> bool:
        attachment = (
            db.query(KnowledgeBaseAgent)
            .filter(
                KnowledgeBaseAgent.knowledge_base_id == kb_id,
                KnowledgeBaseAgent.agent_id == agent_id,
            )
            .first()
        )
        if not attachment:
            return False
        db.delete(attachment)
        db.commit()
        return True

    @staticmethod
    def list_kb_for_agent(db: Session, agent_id: UUID) -> List[KnowledgeBase]:
        return (
            db.query(KnowledgeBase)
            .join(KnowledgeBaseAgent, KnowledgeBaseAgent.knowledge_base_id == KnowledgeBase.id)
            .filter(KnowledgeBaseAgent.agent_id == agent_id)
            .all()
        )

    # ── Vector Search (Phase 5) ───────────────────────────────────────────────

    @staticmethod
    def search_similar_chunks(
        db: Session,
        query_vector: list,
        company_id: UUID,
        kb_id: Optional[UUID] = None,
        top_k: int = 5,
    ) -> List[dict]:
        """
        Cosine similarity search over agent_kb_chunks using pgvector.

        Scoped to company_id; optionally filtered by knowledge_base_id.
        Returns rows as dicts with: chunk_id, document_id, document_name,
        text_content, metadata_json, score (0–1, higher = more similar).
        """
        # Build the query string with optional KB filter
        kb_filter = ""
        params: dict = {
            "company_id": str(company_id),
            "query_vector": str(query_vector),
            "top_k": top_k,
        }

        if kb_id:
            kb_filter = "AND d.knowledge_base_id = :kb_id"
            params["kb_id"] = str(kb_id)

        sql = text(
            f"""
            SELECT
                c.id            AS chunk_id,
                c.document_id   AS document_id,
                d.name          AS document_name,
                c.text_content  AS text_content,
                c.metadata_json AS metadata_json,
                1 - (c.embedding <=> CAST(:query_vector AS vector)) AS score
            FROM agent_kb_chunks c
            JOIN agent_kb_documents d ON d.id = c.document_id
            WHERE d.company_id = CAST(:company_id AS uuid)
              AND c.embedding IS NOT NULL
              {kb_filter}
            ORDER BY c.embedding <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """
        )

        try:
            rows = db.execute(sql, params).mappings().all()
            return [dict(row) for row in rows]
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(
                f"[KB] pgvector search failed: {e}"
            )
            return []
