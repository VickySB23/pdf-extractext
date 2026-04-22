"""
Servicio de orquestación para la generación de resúmenes.
Aplica el principio de Responsabilidad Única (SRP) coordinando
la extracción de texto, la comunicación con la IA y la persistencia.
"""

from uuid import UUID 

from app.application.interfaces.ai_provider import AIProvider
from app.application.interfaces.summary_repository import Summary, SummaryRepository
from app.application.services.pdf_service import PDFService


class SummaryService:
    """Contiene la lógica de negocio principal (Casos de Uso) de la aplicación."""
    def __init__(
        self,
        pdf_service: PDFService,
        ai_provider: AIProvider,
        repository: SummaryRepository,
    ):
        # Inyección de dependencias para facilitar el testing (TDD) y desacoplar código
        self._pdf_service = pdf_service
        self._ai_provider = ai_provider
        self._repository = repository

    async def create_summary(self, file_content: bytes, filename: str) -> Summary:
        """
        Procesa un PDF nuevo, verifica duplicados y genera un resumen con IA.

        Argumentos:
            file_content: Contenido binario del archivo PDF.
            filename: Nombre original del archivo.

        Retorna:
            Summary: Entidad con el resumen guardado.
            
        Excepciones:
            ValueError: Si el documento ya existe en la base de datos (según su checksum).
        """
        
        extracted = self._pdf_service.extract_text(file_content, filename)
        
        # Regla de negocio: Evitar procesar archivos duplicados para ahorrar consumo de API
        if await self._repository.exists_by_checksum(extracted.checksum):
            raise ValueError("Un resumen para este archivo ya existe en la base de datos.") 
        
        ai_response = await self._ai_provider.generate_summary(extracted.text)

        summary = Summary(
            id=None,
            original_filename=filename,
            summary_text=ai_response.content,
            full_text=extracted.text,
            checksum=extracted.checksum,
            created_at=None,
        )
        return await self._repository.save(summary)

    async def get_summary(self, summary_id: UUID) -> Summary | None: 
        """Recupera un resumen específico por su identificador único."""
        return await self._repository.get_by_id(summary_id)

    async def list_summaries(self, limit: int = 100) -> list[Summary]:
        """Devuelve una lista paginada de los resúmenes generados."""
        return await self._repository.get_all(limit)
    
    async def delete_summary(self, summary_id: UUID) -> bool:  
        """Elimina un resumen de la base de datos de forma permanente."""
        return await self._repository.delete(summary_id)