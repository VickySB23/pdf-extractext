"""
Pruebas de integración de la capa de Presentación (API).
Verifica que los endpoints HTTP respondan correctamente usando un cliente de pruebas.
"""
import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from unittest.mock import AsyncMock
from app.main import app
from app.application.interfaces.document_repository import DocumentRecord
from app.core import get_settings
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

def test_create_document_rejects_empty_file():
    mock_service.create_document.reset_mock()

    response = client.post(
        "/api/documents",
        files={"file": ("empty.pdf", b"", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "El archivo está vacío"
    mock_service.create_document.assert_not_called()

def test_create_document_accepts_pdf_extension_case_insensitive():
    mock_service.create_document.reset_mock()
    mock_service.create_document.side_effect = None
    mock_service.create_document.return_value = DocumentRecord(
        id=uuid.uuid4(),
        original_filename="DOCUMENTO.PDF",
        full_text="texto extraido",
        checksum="abcd1234",
        created_at=datetime.now(timezone.utc),
    )

    response = client.post(
        "/api/documents",
        files={"file": ("DOCUMENTO.PDF", b"%PDF-1.7 contenido", "application/pdf")},
    )

    assert response.status_code == 200
    assert response.json()["original_filename"] == "DOCUMENTO.PDF"
    mock_service.create_document.assert_called_once()

def test_create_document_rejects_file_without_pdf_magic_bytes():
    mock_service.create_document.reset_mock()

    response = client.post(
        "/api/documents",
        files={"file": ("fake.pdf", b"contenido que no es pdf", "application/pdf")},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "El contenido no corresponde a un PDF válido"
    mock_service.create_document.assert_not_called()

def test_create_document_rejects_file_exceeding_max_size():
    mock_service.create_document.reset_mock()
    oversized_pdf = b"%PDF-" + b"x" * get_settings().max_upload_size_bytes

    response = client.post(
        "/api/documents",
        files={"file": ("large.pdf", oversized_pdf, "application/pdf")},
    )

    assert response.status_code == 413
    assert "tamaño máximo permitido" in response.json()["detail"]
    mock_service.create_document.assert_not_called()

def test_create_document_returns_400_when_pdf_has_no_extractable_text():
    mock_service.create_document.reset_mock()
    mock_service.create_document.side_effect = ValueError("No se encontró texto extraíble en el PDF.")

    try:
        response = client.post(
            "/api/documents",
            files={"file": ("scanned.pdf", b"%PDF-1.7 contenido sin texto", "application/pdf")},
        )

        assert response.status_code == 400
        assert response.json()["detail"] == "No se encontró texto extraíble en el PDF."
        mock_service.create_document.assert_called_once()
    finally:
        mock_service.create_document.side_effect = None
