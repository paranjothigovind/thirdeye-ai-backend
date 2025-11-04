"""RAG component tests"""
import pytest
from app.rag.splitters import DocumentSplitter
from app.rag.guardrails import Guardrails


def test_document_splitter():
    """Test document splitting"""
    splitter = DocumentSplitter(chunk_size=100, chunk_overlap=20)
    
    text = "This is a test document. " * 50
    chunks = splitter.split_text(text, metadata={"source": "test"})
    
    assert len(chunks) > 1
    assert all("content" in chunk for chunk in chunks)
    assert all(chunk["source"] == "test" for chunk in chunks)


def test_guardrails_medical_query():
    """Test guardrails for medical queries"""
    guardrails = Guardrails()
    
    result = guardrails.check_query("Can you diagnose my headache?")
    assert not result["is_safe"]
    assert "medical_query" in result["issues"]


def test_guardrails_emergency():
    """Test guardrails for emergency queries"""
    guardrails = Guardrails()
    
    result = guardrails.check_query("I'm having a crisis")
    assert not result["is_safe"]
    assert "emergency" in result["issues"]


def test_guardrails_safe_query():
    """Test guardrails for safe queries"""
    guardrails = Guardrails()
    
    result = guardrails.check_query("How do I practice Trataka?")
    assert result["is_safe"]
    assert len(result["issues"]) == 0


def test_citation_extraction():
    """Test citation extraction"""
    from app.rag.chains import RAGChain
    
    chain = RAGChain()
    response = "Practice Trataka [Source: Yoga Guide, page 42] for 5 minutes [Source: Safety Manual, page 10]."
    
    citations = chain.extract_citations(response)
    assert len(citations) == 2
    assert citations[0]["title"] == "Yoga Guide"
    assert citations[0]["reference"] == "page 42"