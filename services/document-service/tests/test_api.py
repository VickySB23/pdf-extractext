"""
Pruebas de integración de la capa de Presentación (API).
Verifica que los endpoints HTTP respondan correctamente usando un cliente de pruebas.
"""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock

from app.application.interfaces.document_repository import DocumentRecord
from app.application.interfaces.text_extractor import (
    EncryptedPDFError,
    ExtractorProtocolError,
    ExtractorUnavailableError,
    FileTooLargeError,
    InvalidPDFError,
    NoTextError,
    TextExtractionError,
)
from app.core import get_settings
from app.main import app
from app.presentation.routers.document_router import get_document_service

# 1. ARRANGE
mock_service = AsyncMock()
mock_service.list_documents.return_value = []

app.dependency_overrides[get_document_service] = lambda: mock_service

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_mock_service():
    mock_service.create_document.reset_mock()
    mock_service.create_document.side_effect = None
    mock_service.create_document.return_value = None
    yield
    mock_service.create_document.side_effect = None
    mock_service.create_document.return_value = None


def post_document(
    filename: str = "documento.pdf",
    content: bytes = b"%PDF-1.7 contenido",
):
    return client.post(
        "/api/documents",
        files={"file": (filename, content, "application/pdf")},
    )


def test_get_documents_empty_list():
    """Verifica el comportamiento del listado cuando la base de datos está vacía."""

    response = client.get("/api/documents")

    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 0


def test_create_document_rejects_empty_file():
    response = post_document(filename="empty.pdf", content=b"")

    assert response.status_code == 400
    assert response.json()["detail"] == "El archivo está vacío"
    mock_service.create_document.assert_not_called()


def test_create_document_accepts_pdf_extension_case_insensitive():
    mock_service.create_document.return_value = DocumentRecord(
        id=uuid.uuid4(),
        original_filename="DOCUMENTO.PDF",
        full_text="texto extraido",
        checksum="abcd1234",
        created_at=datetime.now(timezone.utc),
    )

    response = post_document(filename="DOCUMENTO.PDF")

    assert response.status_code == 200
    assert response.json()["original_filename"] == "DOCUMENTO.PDF"
    mock_service.create_document.assert_called_once()


def test_create_document_rejects_file_without_pdf_magic_bytes():
    response = post_document(content=b"contenido que no es pdf")

    assert response.status_code == 400
    assert response.json()["detail"] == "El contenido no corresponde a un PDF válido"
    mock_service.create_document.assert_not_called()


def test_create_document_rejects_file_exceeding_max_size():
    oversized_pdf = b"%PDF-" + b"x" * get_settings().max_upload_size_bytes

    response = post_document(filename="large.pdf", content=oversized_pdf)

    assert response.status_code == 413
    assert "tamaño máximo permitido" in response.json()["detail"]
    mock_service.create_document.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        NoTextError("No se encontró texto extraíble en el PDF."),
        InvalidPDFError("No se pudo procesar el archivo PDF."),
        EncryptedPDFError("El PDF está protegido con contraseña."),
    ],
)
def test_create_document_returns_400_for_extraction_input_errors(error):
    mock_service.create_document.side_effect = error

    response = post_document()

    assert response.status_code == 400
    assert response.json()["detail"] == str(error)
    mock_service.create_document.assert_called_once()


def test_create_document_returns_400_for_duplicate():
    mock_service.create_document.side_effect = ValueError(
        "Un documento con este mismo contenido ya existe en la base de datos."
    )

    response = post_document()

    assert response.status_code == 400
    assert response.json()["detail"] == (
        "Un documento con este mismo contenido ya existe en la base de datos."
    )
    mock_service.create_document.assert_called_once()


def test_create_document_returns_413_for_file_too_large_error():
    mock_service.create_document.side_effect = FileTooLargeError(
        "El archivo excede el tamaño máximo permitido."
    )

    response = post_document()

    assert response.status_code == 413
    assert response.json()["detail"] == "El archivo excede el tamaño máximo permitido."
    mock_service.create_document.assert_called_once()


def test_create_document_returns_502_for_protocol_error():
    mock_service.create_document.side_effect = ExtractorProtocolError(
        "El servicio de extracción devolvió una respuesta inválida."
    )

    response = post_document()

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "El servicio de extracción devolvió una respuesta inválida."
    )
    mock_service.create_document.assert_called_once()


def test_create_document_returns_502_for_unhandled_extraction_error():
    mock_service.create_document.side_effect = TextExtractionError(
        "detalle interno que no debe exponerse"
    )

    response = post_document()

    assert response.status_code == 502
    assert response.json()["detail"] == (
        "No se pudo procesar la extracción del documento."
    )
    assert "detalle interno" not in response.text
    mock_service.create_document.assert_called_once()


def test_create_document_returns_503_for_unavailable_extractor():
    mock_service.create_document.side_effect = ExtractorUnavailableError(
        "El servicio de extracción no está disponible. Intentá nuevamente."
    )

    response = post_document()

    assert response.status_code == 503
    assert "retry-after" not in response.headers
    mock_service.create_document.assert_called_once()


def test_create_document_propagates_valid_retry_after():
    mock_service.create_document.side_effect = ExtractorUnavailableError(
        "El servicio de extracción está saturado. Reintentá en unos segundos.",
        retry_after="7",
    )

    response = post_document()

    assert response.status_code == 503
    assert response.headers["retry-after"] == "7"
    mock_service.create_document.assert_called_once()


def test_create_document_omits_invalid_retry_after():
    mock_service.create_document.side_effect = ExtractorUnavailableError(
        "El servicio de extracción está saturado.",
        retry_after="7\nX-Invalid-Header: 1",
    )

    response = post_document()

    assert response.status_code == 503
    assert "retry-after" not in response.headers
    assert "x-invalid-header" not in response.headers
    mock_service.create_document.assert_called_once()
