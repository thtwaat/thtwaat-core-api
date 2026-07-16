import pytest
from app.agent_platform.knowledge.schemas import KnowledgeBaseCreate, DocumentCreate
from app.agent_platform.knowledge.routers import router

def test_knowledge_base_schemas():
    kb = KnowledgeBaseCreate(name="Test KB", description="A test knowledge base")
    assert kb.name == "Test KB"
    
def test_document_schemas():
    doc = DocumentCreate(name="test.pdf", source_type="PDF")
    assert doc.name == "test.pdf"
    assert doc.source_type == "PDF"

def test_router_prefix():
    assert router.prefix == "/v2/knowledge"
