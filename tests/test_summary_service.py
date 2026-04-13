import pytest
from unittest.mock import AsyncMock, MagicMock
from app.application.services.summary_service import SummaryService
from app.application.interfaces.ai_provider import AIResponse
from app.application.services.pdf_service import ExtractedPDF

@pytest.mark.asyncio
async def test_create_summary_orchestration():
    mock_pdf_service = MagicMock()
    mock_pdf_service.extract_text.return_value = ExtractedPDF(
        filename="test.pdf", text="texto extraido", page_count=1, character_count=14
    )
    
    mock_ai_provider = AsyncMock()
    mock_ai_provider.generate_summary.return_value = AIResponse(
        content="resumen generado por la IA", model="llama-3", tokens_used=10
    )
    
    mock_repository = AsyncMock()
    mock_repository.save.side_effect = lambda summary: summary 
    
    service = SummaryService(mock_pdf_service, mock_ai_provider, mock_repository)
    result = await service.create_summary(b"bytes falsos", "test.pdf")
    
    assert result.original_filename == "test.pdf"
    assert result.summary_text == "resumen generado por la IA"
    
    mock_pdf_service.extract_text.assert_called_once()
    mock_ai_provider.generate_summary.assert_called_once_with("texto extraido")
    mock_repository.save.assert_called_once()