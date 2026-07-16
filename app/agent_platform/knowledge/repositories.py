from sqlalchemy.orm import Session
from uuid import UUID
from app.agent_platform.knowledge.models.knowledge_base import KnowledgeBase
from app.agent_platform.knowledge.models.document import Document
from app.agent_platform.knowledge.schemas import KnowledgeBaseCreate, DocumentCreate

class KnowledgeRepository:
    
    @staticmethod
    def create_knowledge_base(db: Session, company_id: UUID, kb_in: KnowledgeBaseCreate) -> KnowledgeBase:
        db_kb = KnowledgeBase(company_id=company_id, **kb_in.model_dump())
        db.add(db_kb)
        db.commit()
        db.refresh(db_kb)
        return db_kb
        
    @staticmethod
    def get_knowledge_bases(db: Session, company_id: UUID):
        return db.query(KnowledgeBase).filter(KnowledgeBase.company_id == company_id).all()
        
    @staticmethod
    def create_document(db: Session, company_id: UUID, doc_in: DocumentCreate) -> Document:
        db_doc = Document(company_id=company_id, **doc_in.model_dump())
        db.add(db_doc)
        db.commit()
        db.refresh(db_doc)
        return db_doc
        
    @staticmethod
    def get_documents(db: Session, company_id: UUID):
        return db.query(Document).filter(Document.company_id == company_id).all()
        
    @staticmethod
    def get_document(db: Session, doc_id: UUID, company_id: UUID):
        return db.query(Document).filter(Document.id == doc_id, Document.company_id == company_id).first()
