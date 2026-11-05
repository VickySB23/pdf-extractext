"""
Pruebas unitarias para el orquestador principal (DocumentService).
Verifica que la capa de aplicación coordine correctamente el flujo de datos.
"""
import hashlib
from unittest.mock import AsyncMock

import pytest

from app.application.interfaces.text_extractor import (
    EncryptedPDFError,
    ExtractedText,
    ExtractorProtocolError,
    ExtractorUnavailableError,
    FileTooLargeError,
    InvalidPDFError,
    NoTextError,
)
from app.application.services.document_service import DocumentService


class FakeExtractor:
    def __init__(self, result: ExtractedText | None = None, error: Exception | None = None):
        self.result = result
        self.error = error
        self.calls: list[tuple[str, bytes]] = []

    async def extract(self, filename: str, content: bytes) -> ExtractedText:
        self.calls.append((filename, content))
        if self.error is not None:
            raise self.error
        assert self.result is not None
        return self.result


@pytest.mark.asyncio
async def test_create_document_orchestration_and_checksum():
    """Verifica el caso de éxito, el checksum y la persistencia."""
    text = "texto extraído"
    extractor = FakeExtractor(ExtractedText(text=text, pages=2))

    mock_repository = AsyncMock()
    mock_repository.exists_by_checksum.return_value = False
    mock_repository.save.side_effect = lambda doc: doc

    service = DocumentService(extractor, mock_repository)

    result = await service.create_document(b"bytes falsos", "test.pdf")

    expected_checksum = hashlib.sha256(b"bytes falsos").hexdigest()
    assert result.original_filename == "test.pdf"
    assert result.full_text == text
    assert result.checksum == expected_checksum
    assert extractor.calls == [("test.pdf", b"bytes falsos")]
    mock_repository.exists_by_checksum.assert_awaited_once_with(expected_checksum)
    mock_repository.save.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_document_stores_stripped_text_and_hashes_the_file():
    extractor = FakeExtractor(ExtractedText(text="  texto con espacios  \n", pages=1))

    mock_repository = AsyncMock()
    mock_repository.exists_by_checksum.return_value = False
    mock_repository.save.side_effect = lambda doc: doc

    service = DocumentService(extractor, mock_repository)

    result = await service.create_document(b"%PDF-", "espacios.pdf")

    expected_checksum = hashlib.sha256(b"%PDF-").hexdigest()
    assert result.full_text == "texto con espacios"
    assert result.checksum == expected_checksum


@pytest.mark.parametrize("text", ["", "   ", "\n\t "])
@pytest.mark.asyncio
async def test_create_document_does_not_save_when_text_is_empty(text):
    extractor = FakeExtractor(ExtractedText(text=text, pages=1))
    mock_repository = AsyncMock()

    service = DocumentService(extractor, mock_repository)

    with pytest.raises(NoTextError, match="No se encontró texto extraíble"):
        await service.create_document(b"%PDF-1.7 sin texto", "escaneado.pdf")

    mock_repository.exists_by_checksum.assert_not_called()
    mock_repository.save.assert_not_called()


@pytest.mark.asyncio
async def test_create_document_rejects_duplicate_checksum():
    extractor = FakeExtractor(ExtractedText(text="contenido duplicado", pages=1))
    mock_repository = AsyncMock()
    mock_repository.exists_by_checksum.return_value = True

    service = DocumentService(extractor, mock_repository)

    with pytest.raises(ValueError, match="mismo contenido ya existe"):
        await service.create_document(b"%PDF-1.7 duplicado", "duplicado.pdf")

    expected_checksum = hashlib.sha256(b"%PDF-1.7 duplicado").hexdigest()
    mock_repository.exists_by_checksum.assert_awaited_once_with(expected_checksum)
    mock_repository.save.assert_not_called()


@pytest.mark.parametrize(
    "error",
    [
        InvalidPDFError("PDF inválido"),
        EncryptedPDFError("PDF cifrado"),
        FileTooLargeError("Archivo demasiado grande"),
        ExtractorUnavailableError("Servicio no disponible"),
        ExtractorProtocolError("Respuesta inválida"),
    ],
)
@pytest.mark.asyncio
async def test_create_document_does_not_save_when_extraction_fails(error):
    extractor = FakeExtractor(error=error)
    mock_repository = AsyncMock()

    service = DocumentService(extractor, mock_repository)

    with pytest.raises(type(error)):
        await service.create_document(b"%PDF-1.7 contenido", "fallo.pdf")

    mock_repository.exists_by_checksum.assert_not_called()
    mock_repository.save.assert_not_called()
