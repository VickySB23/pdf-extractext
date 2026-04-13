from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from app.main import app
from app.presentation.routers.pdf_summary import get_summary_service

mock_service = AsyncMock()
mock_service._ai_provider.health_check.return_value = True
mock_service.list_summaries.return_value = []

app.dependency_overrides[get_summary_service] = lambda: mock_service

client = TestClient(app)

def test_health_check_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["ai_provider_available"] is True

def test_get_summaries_empty_list():
    response = client.get("/api/summaries")   
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["summaries"] == []