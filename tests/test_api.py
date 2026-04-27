"""
Pruebas de integración de la capa de Presentación (API).
Verifica que los endpoints HTTP respondan correctamente usando un cliente de pruebas.
"""
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from app.main import app
from app.presentation.routers.document_router import get_document_service

# 1. ARRANGE
mock_service = AsyncMock()
mock_service.list_documents.return_value = []

app.dependency_overrides[get_document_service] = lambda: mock_service

client = TestClient(app)

def test_get_documents_empty_list():
    """Verifica el comportamiento del listado cuando la base de datos está vacía."""
    
    # 2. ACT
    response = client.get("/api/documents")   
    
    # 3. ASSERT
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0