"""
Pruebas unitarias para el orquestador principal (SummaryService).
Verifica que la capa de aplicación coordine correctamente el flujo de datos
entre el extractor de PDFs, la API de IA y el repositorio.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock
from app.application.services.summary_service import SummaryService
from app.application.interfaces.ai_provider import AIResponse
from app.application.services.pdf_service import ExtractedPDF

@pytest.mark.asyncio
async def test_create_summary_orchestration():
    """Verifica el caso de éxito donde se lee, se resume y se guarda un PDF."""
    
    # 1. ARRANGE (Preparar: Simular los 3 componentes que usa el orquestador)
    mock_pdf_service = MagicMock()
    mock_pdf_service.extract_text.return_value = ExtractedPDF(
        filename="test.pdf", text="texto extraido", page_count=1, character_count=14
    )
    
    mock_ai_provider = AsyncMock()
    mock_ai_provider.generate_summary.return_value = AIResponse(
        content="resumen generado por la IA", model="llama-3", tokens_used=10
    )
    
    mock_repository = AsyncMock()
    # Simulamos que al guardar, la base de datos devuelve la misma entidad
    mock_repository.save.side_effect = lambda summary: summary 
    # Simulamos que el archivo NO existe para pasar la validación anti-duplicados
    mock_repository.exists_by_checksum.return_value = False 
    
    service = SummaryService(mock_pdf_service, mock_ai_provider, mock_repository)
    
    # 2. ACT (Ejecutar: Iniciar el proceso de resumen completo)
    result = await service.create_summary(b"bytes falsos", "test.pdf")
    
    # 3. ASSERT (Comprobar: Validar resultados y que los métodos fueron llamados)
    assert result.original_filename == "test.pdf"
    assert result.summary_text == "resumen generado por la IA"
    
    # Verificamos la orquestación (que el servicio delegó las tareas correctas)
    mock_pdf_service.extract_text.assert_called_once()
    mock_ai_provider.generate_summary.assert_called_once_with("texto extraido")
    mock_repository.save.assert_called_once()