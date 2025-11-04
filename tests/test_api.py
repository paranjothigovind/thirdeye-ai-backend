"""API endpoint tests"""
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health_check():
    """Test health endpoint"""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "timestamp" in data


def test_readiness_check():
    """Test readiness endpoint"""
    response = client.get("/api/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"


def test_chat_endpoint_validation():
    """Test chat endpoint validation"""
    # Empty messages
    response = client.post("/api/chat", json={"messages": []})
    assert response.status_code == 400
    
    # Invalid message format
    response = client.post("/api/chat", json={"messages": [{"invalid": "format"}]})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_ingest_validation():
    """Test ingest endpoint validation"""
    # No file or URLs
    response = client.post("/api/ingest")
    assert response.status_code == 422