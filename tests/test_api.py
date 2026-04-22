"""
Pruebas de integración de la capa de Presentación (API).
Verifica que los endpoints HTTP respondan correctamente usando un cliente de pruebas
y dependencias simuladas (Mocks) para no hacer llamadas reales a la IA o Base de Datos.
"""
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from app.main import app
from app.presentation.routers.pdf_summary import get_summary_service

# 1. ARRANGE (Configuración global de Mocks para la suite de pruebas de la API)
mock_service = AsyncMock()
mock_service._ai_provider.health_check.return_value = True
mock_service.list_summaries.return_value = []

# Inyección de la dependencia simulada
app.dependency_overrides[get_summary_service] = lambda: mock_service

client = TestClient(app)

def test_health_check_endpoint():
    """Verifica que el endpoint de estado de salud del sistema responda correctamente."""
    
    # 2. ACT (Ejecutar: Hacemos una petición GET simulada)
    response = client.get("/api/health")
    
    # 3. ASSERT (Comprobar: Validamos el código HTTP y el JSON devuelto)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert data["ai_provider_available"] is True

def test_get_summaries_empty_list():
    """Verifica el comportamiento del listado cuando la base de datos está vacía."""
    
    # 2. ACT
    response = client.get("/api/summaries")   
    
    # 3. ASSERT
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["summaries"] == []