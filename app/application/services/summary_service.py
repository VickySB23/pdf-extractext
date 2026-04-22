"""Summary generation service - orchestrates PDF extraction and AI summarization."""

from uuid import UUID 

from app.application.interfaces.ai_provider import AIProvider
from app.application.interfaces.summary_repository import Summary, SummaryRepository
from app.application.services.pdf_service import PDFService


class SummaryService:
    def __init__(
        self,
        pdf_service: PDFService,
        ai_provider: AIProvider,
        repository: SummaryRepository,
    ):
        self._pdf_service = pdf_service
        self._ai_provider = ai_provider
        self._repository = repository

    async def create_summary(self, file_content: bytes, filename: str) -> Summary:
        extracted = self._pdf_service.extract_text(file_content, filename)
        
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
        return await self._repository.get_by_id(summary_id)

    async def list_summaries(self, limit: int = 100) -> list[Summary]:
        return await self._repository.get_all(limit)
    
    async def delete_summary(self, summary_id: UUID) -> bool:  
        return await self._repository.delete(summary_id)