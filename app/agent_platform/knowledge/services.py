"""
app/agent_platform/knowledge/services.py
Knowledge Base service layer.

Phase 1:  KB CRUD + file upload (DONE)
Phase 2:  Text extraction — PDF, DOCX, TXT/MD (DONE)
Phase 3:  Chunking — recursive character splitter (DONE)
Phase 4:  Embeddings — Ollama (nomic-embed-text) / Gemini fallback (DONE)
Phase 5:  Vector similarity search via pgvector cosine distance (DONE)
Phase 6:  RAG prompt construction + AI response → see rag_service.py
"""
import logging
import uuid
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, UploadFile

from sqlalchemy.orm import Session

from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBase
from app.agent_platform.knowledge.models.document import Document
from app.agent_platform.knowledge.repositories import KnowledgeRepository
from app.agent_platform.knowledge.schemas import (
    KnowledgeBaseCreate,
    DocumentCreate,
    SearchResult,
)

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".txt", ".md"}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
KB_UPLOAD_DIR = Path("data/knowledge")


class KnowledgeService:

    # ── Knowledge Base CRUD ───────────────────────────────────────────────────

    @staticmethod
    def create_knowledge_base(
        db: Session, company_id: UUID, kb_in: KnowledgeBaseCreate
    ) -> KnowledgeBase:
        return KnowledgeRepository.create_knowledge_base(db, company_id, kb_in)

    @staticmethod
    def get_knowledge_bases(db: Session, company_id: UUID) -> List[KnowledgeBase]:
        return KnowledgeRepository.get_knowledge_bases(db, company_id)

    @staticmethod
    def get_knowledge_base(
        db: Session, kb_id: UUID, company_id: UUID
    ) -> KnowledgeBase:
        kb = KnowledgeRepository.get_knowledge_base(db, kb_id, company_id)
        if not kb:
            raise HTTPException(status_code=404, detail="Knowledge base not found")
        return kb

    @staticmethod
    def delete_knowledge_base(db: Session, kb_id: UUID, company_id: UUID) -> None:
        if not KnowledgeRepository.delete_knowledge_base(db, kb_id, company_id):
            raise HTTPException(status_code=404, detail="Knowledge base not found")

    # ── Document Upload ───────────────────────────────────────────────────────

    @staticmethod
    async def upload_document(
        db: Session,
        company_id: UUID,
        file: UploadFile,
        knowledge_base_id: Optional[UUID] = None,
    ) -> Document:
        """
        Phase 1+2+3+4: Save file → create Document record → trigger indexing.

        The heavy lifting (extraction → chunking → embedding) is done in
        `_index_document()` which is scheduled as a FastAPI BackgroundTask
        by the router; this method only saves the file and returns immediately.
        """
        original_name = file.filename or "unknown"
        ext = Path(original_name).suffix.lower()

        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=415,
                detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
            )

        content = await file.read()
        file_size = len(content)

        if file_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"File too large ({file_size // 1024}KB). Max is {MAX_FILE_SIZE // (1024 * 1024)}MB.",
            )
        if file_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        # Quota: storage + upload size
        try:
            from app.usage.dimensions import UsageDimension
            from app.usage.service import UsageService

            usage = UsageService(db)
            meter = usage.get_or_create_meter(company_id)
            projected = int(meter.storage_bytes or 0) + file_size
            usage.check_quota(company_id, UsageDimension.STORAGE_BYTES, quantity=projected)
            usage.check_quota(company_id, UsageDimension.KNOWLEDGE_UPLOAD_BYTES, quantity=file_size)
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning(f"[KB] usage quota check skipped: {exc}")

        # Save to local KB storage directory (isolated per company)
        company_dir = KB_UPLOAD_DIR / str(company_id)
        company_dir.mkdir(parents=True, exist_ok=True)

        storage_name = f"{uuid.uuid4().hex}{ext}"
        storage_path = company_dir / storage_name

        try:
            with open(storage_path, "wb") as f:
                f.write(content)
        except OSError as e:
            logger.error(f"Failed to write file {storage_path}: {e}")
            raise HTTPException(status_code=500, detail="Failed to save uploaded file.")

        source_type_map = {".pdf": "PDF", ".docx": "DOCX", ".txt": "TXT", ".md": "MD"}
        source_type = source_type_map.get(ext, ext.lstrip(".").upper())

        doc_in = DocumentCreate(
            name=original_name,
            source_type=source_type,
            knowledge_base_id=knowledge_base_id,
            content_metadata={"original_filename": original_name, "extension": ext},
        )

        doc = KnowledgeRepository.create_document(
            db=db,
            company_id=company_id,
            doc_in=doc_in,
            file_path=str(storage_path),
            file_size_bytes=file_size,
        )

        try:
            from app.usage.dimensions import UsageDimension
            from app.usage.service import UsageService

            usage = UsageService(db)
            meter = usage.get_or_create_meter(company_id)
            usage.record(
                company_id,
                UsageDimension.KNOWLEDGE_UPLOAD_BYTES,
                file_size,
                source="knowledge_upload",
                emit_webhook=False,
            )
            usage.record(
                company_id,
                UsageDimension.STORAGE_BYTES,
                int(meter.storage_bytes or 0) + file_size,
                source="knowledge_upload",
            )
        except Exception as exc:
            logger.warning(f"[KB] usage record failed: {exc}")

        logger.info(
            f"[KB] Document uploaded: id={doc.id} name={original_name} "
            f"size={file_size}B company={company_id} — indexing scheduled"
        )
        return doc

    # ── Indexing Pipeline (BackgroundTask) ────────────────────────────────────

    @staticmethod
    async def index_document(doc_id: UUID, company_id: UUID) -> None:
        """
        Full indexing pipeline: extract → chunk → embed → store.
        Designed to be called as a FastAPI BackgroundTask.

        Uses a *fresh* DB session so it can run independently of the
        request-scoped session that was already closed.
        """
        from app.database.database import SessionLocal

        db = SessionLocal()
        try:
            await KnowledgeService._run_indexing(db, doc_id, company_id)
        except Exception as e:
            logger.error(
                f"[KB] Indexing failed for doc={doc_id}: {e}", exc_info=True
            )
            # Best-effort status update
            try:
                KnowledgeRepository.update_document_status(
                    db, doc_id, company_id, "ERROR"
                )
            except Exception:
                pass
        finally:
            db.close()

    @staticmethod
    async def _run_indexing(db: Session, doc_id: UUID, company_id: UUID) -> None:
        """Internal: execute the full extraction → chunk → embed pipeline."""
        from app.agent_platform.knowledge.extractors import ExtractorFactory
        from app.agent_platform.knowledge.chunker import TextChunker
        from app.agent_platform.knowledge.embeddings import EmbeddingService

        doc = KnowledgeRepository.get_document(db, doc_id, company_id)
        if not doc:
            logger.warning(f"[KB] Document {doc_id} not found for indexing")
            return

        logger.info(f"[KB] Indexing started: doc={doc_id} type={doc.source_type}")

        # ── Step 1: Mark as INDEXING ─────────────────────────────────────────
        KnowledgeRepository.update_document_status(db, doc_id, company_id, "INDEXING")

        # ── Step 2: Extract text ─────────────────────────────────────────────
        try:
            extractor = ExtractorFactory.get(doc.source_type)
            extraction = extractor.extract(doc.file_path)
        except Exception as e:
            logger.error(f"[KB] Extraction failed for doc={doc_id}: {e}")
            KnowledgeRepository.update_document_status(db, doc_id, company_id, "ERROR")
            return

        if not extraction.pages:
            logger.warning(f"[KB] No text extracted from doc={doc_id}")
            KnowledgeRepository.update_document_status(db, doc_id, company_id, "ERROR")
            return

        # ── Step 3: Chunk ────────────────────────────────────────────────────
        chunker = TextChunker(chunk_size=800, overlap=100)
        chunk_results = chunker.split_pages(extraction.pages)

        if not chunk_results:
            logger.warning(f"[KB] No chunks produced for doc={doc_id}")
            KnowledgeRepository.update_document_status(db, doc_id, company_id, "ERROR")
            return

        # ── Step 4: Delete old chunks (if reindexing) ────────────────────────
        KnowledgeRepository.delete_chunks_by_document(db, doc_id)

        # ── Step 5: Save chunks ──────────────────────────────────────────────
        chunk_dicts = [
            {
                "chunk_index": cr.chunk_index,
                "text_content": cr.text_content,
                "metadata_json": cr.metadata_json,
            }
            for cr in chunk_results
        ]
        db_chunks = KnowledgeRepository.create_chunks(db, doc_id, chunk_dicts)

        # ── Step 6: Embed + store vectors ────────────────────────────────────
        texts = [c.text_content for c in db_chunks]
        try:
            vectors = await EmbeddingService.embed_batch(texts)
        except Exception as e:
            logger.error(f"[KB] Embedding failed for doc={doc_id}: {e}")
            KnowledgeRepository.update_document_status(db, doc_id, company_id, "ERROR")
            return

        # Determine which model was actually used (Ollama or Gemini)
        from app.agent_platform.knowledge.embeddings import (
            OLLAMA_EMBED_MODEL,
            GEMINI_EMBED_MODEL,
            EMBEDDING_DIMENSIONS,
        )

        # Write embeddings into the chunk rows
        try:
            for db_chunk, vector in zip(db_chunks, vectors):
                db_chunk.embedding = vector
                KnowledgeRepository.store_embedding_meta(
                    db,
                    chunk_id=db_chunk.id,
                    model_name=OLLAMA_EMBED_MODEL,
                    dimensions=EMBEDDING_DIMENSIONS,
                )
            db.commit()
        except Exception as e:
            logger.error(f"[KB] Failed to store embeddings for doc={doc_id}: {e}")
            KnowledgeRepository.update_document_status(db, doc_id, company_id, "ERROR")
            return

        # ── Step 7: Mark as INDEXED ──────────────────────────────────────────
        KnowledgeRepository.update_document_status(db, doc_id, company_id, "INDEXED")
        logger.info(
            f"[KB] Indexing complete: doc={doc_id} "
            f"chunks={len(db_chunks)} company={company_id}"
        )

        # ── Dispatch in-app notification event ────────────────────────────────
        try:
            from app.notifications.events import NotificationEventBus
            doc_name = doc.original_name if hasattr(doc, "original_name") else str(doc_id)
            NotificationEventBus.dispatch(
                event_type="document.indexed",
                db=db,
                company_id=company_id,
                user_id=None,
                data={"document_name": doc_name},
            )
        except Exception:
            pass  # Never let notification failure break indexing

    # ── Document CRUD ─────────────────────────────────────────────────────────

    @staticmethod
    def get_documents(
        db: Session,
        company_id: UUID,
        kb_id: Optional[UUID] = None,
    ) -> List[Document]:
        return KnowledgeRepository.get_documents(db, company_id, kb_id)

    @staticmethod
    def get_document(db: Session, doc_id: UUID, company_id: UUID) -> Document:
        doc = KnowledgeRepository.get_document(db, doc_id, company_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        return doc

    @staticmethod
    def delete_document(db: Session, doc_id: UUID, company_id: UUID) -> None:
        """Delete document record + physical file."""
        doc = KnowledgeRepository.get_document(db, doc_id, company_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")

        if doc.file_path:
            try:
                path = Path(doc.file_path)
                if path.exists():
                    path.unlink()
                    logger.info(f"[KB] Deleted file: {path}")
            except OSError as e:
                logger.warning(f"[KB] Could not delete file {doc.file_path}: {e}")

        KnowledgeRepository.delete_chunks_by_document(db, doc_id)
        KnowledgeRepository.delete_document(db, doc_id, company_id)
        logger.info(f"[KB] Document deleted: id={doc_id} company={company_id}")

    # ── Agent Attachment ──────────────────────────────────────────────────────

    @staticmethod
    def attach_knowledge_base_to_agent(
        db: Session, kb_id: UUID, agent_id: UUID
    ):
        return KnowledgeRepository.attach_kb_to_agent(db, kb_id, agent_id)

    # ── Search (Phase 5: real pgvector cosine similarity) ─────────────────────

    @staticmethod
    def search_knowledge_base(
        db: Session,
        query: str,
        top_k: int,
        company_id: UUID,
        kb_id: Optional[UUID] = None,
    ) -> List[SearchResult]:
        """
        Semantic similarity search over indexed document chunks.

        Embeds the query synchronously (blocking), then runs a pgvector
        cosine-distance query scoped to the company (and optionally one KB).
        Returns an empty list if no chunks are indexed yet.
        """
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        from app.agent_platform.knowledge.embeddings import EmbeddingService

        # Embed the query. When called from an async route (RAG), a running
        # event loop already exists — asyncio.run / new_event_loop would fail,
        # so fall back to a dedicated thread with its own loop.
        try:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                query_vector = asyncio.run(EmbeddingService.embed_text(query))
            else:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    query_vector = pool.submit(
                        asyncio.run, EmbeddingService.embed_text(query)
                    ).result()
        except Exception as e:
            logger.error(f"[KB] Query embedding failed: {e}")
            return []

        # Run cosine similarity search
        raw_results = KnowledgeRepository.search_similar_chunks(
            db=db,
            query_vector=query_vector,
            company_id=company_id,
            kb_id=kb_id,
            top_k=top_k,
        )

        return [
            SearchResult(
                chunk_id=str(row["chunk_id"]),
                document_id=str(row["document_id"]),
                document_name=row["document_name"],
                text=row["text_content"],
                score=float(row["score"]),
                metadata=row.get("metadata_json", {}),
            )
            for row in raw_results
        ]

    # ── Reindex ───────────────────────────────────────────────────────────────

    @staticmethod
    async def reindex_document(
        db: Session, doc_id: UUID, company_id: UUID
    ) -> Document:
        """Reset status to PENDING — caller should schedule index_document()."""
        doc = KnowledgeRepository.get_document(db, doc_id, company_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        doc.status = "PENDING"
        db.commit()
        db.refresh(doc)
        return doc
