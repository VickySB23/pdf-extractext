"""
Pruebas unitarias para el orquestador principal (DocumentService).
Verifica que la capa de aplicación coordine correctamente el flujo de datos.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.application.services.document_service import DocumentService
from app.application.services.pdf_service import ExtractedPDF

@pytest.mark.asyncio
async def test_create_document_orchestration():
    """Verifica el caso de éxito donde se extrae texto y se guarda."""
    
    # 1. ARRANGE
    mock_pdf_service = MagicMock()
    # Aquí estaba el error: Agregamos los parámetros que faltaban
    mock_pdf_service.extract_text.return_value = ExtractedPDF(
            filename="test.pdf",
            text="texto extraido",
            checksum="abcd1234"
        )
    
    mock_repository = AsyncMock()
    mock_repository.save.side_effect = lambda doc: doc 
    mock_repository.exists_by_checksum.return_value = False 
    
    service = DocumentService(mock_pdf_service, mock_repository)
    
    # 2. ACT 
    result = await service.create_document(b"bytes falsos", "test.pdf")
    
    # 3. ASSERT
    assert result.original_filename == "test.pdf"
    assert result.full_text == "texto extraido"
    assert result.checksum == "abcd1234"
    
    # Verificamos la orquestación
    mock_pdf_service.extract_text.assert_called_once()
    mock_repository.save.assert_called_once()

@pytest.mark.asyncio
async def test_create_document_does_not_save_when_pdf_has_no_text():
    mock_pdf_service = MagicMock()
    mock_pdf_service.extract_text.side_effect = ValueError("No se encontró texto extraíble en el PDF.")

    mock_repository = AsyncMock()

    service = DocumentService(mock_pdf_service, mock_repository)

    with pytest.raises(ValueError) as exc_info:
        await service.create_document(b"%PDF-1.7 sin texto", "escaneado.pdf")

    assert "No se encontró texto extraíble" in str(exc_info.value)
    mock_repository.exists_by_checksum.assert_not_called()
    mock_repository.save.assert_not_called()
