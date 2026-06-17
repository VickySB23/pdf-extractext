"""
Módulo de servicios de aplicación para la gestión de documentos.
Actúa como orquestador de la lógica de negocio, aplicando el principio de Responsabilidad Única (SRP).
"""
import asyncio
from uuid import UUID
from app.application.interfaces.document_repository import DocumentRecord, DocumentRepository
from app.application.services.pdf_service import PDFService
from app.core.logger import logger

class DocumentService:
    def __init__(self, pdf_service: PDFService, repository: DocumentRepository):
        self._pdf_service = pdf_service
        self._repository = repository

    async def create_document(self, file_content: bytes, filename: str) -> DocumentRecord:
        logger.info(f"Iniciando procesamiento del documento: '{filename}'")
        extracted = await asyncio.to_thread(self._pdf_service.extract_text, file_content, filename)
        
        if await self._repository.exists_by_checksum(extracted.checksum):
            logger.warning(f"Rechazado: El documento '{filename}' ya existe (Duplicado de Checksum).")
            raise ValueError("Un documento con este mismo contenido ya existe en la base de datos.")
        
        document = DocumentRecord(
            id=None,
            original_filename=filename,
            full_text=extracted.text,
            checksum=extracted.checksum,
            created_at=None,
        )
        
        saved_doc = await self._repository.save(document)
        logger.info(f"Documento '{filename}' guardado exitosamente con ID: {saved_doc.id}")
        return saved_doc

    async def get_document(self, doc_id: UUID) -> DocumentRecord | None:
        """Recupera un documento específico mediante su identificador único."""
        return await self._repository.get_by_id(doc_id)

    async def list_documents(self, limit: int = 100) -> list[DocumentRecord]:
        """Obtiene una lista paginada de todos los documentos almacenados."""
        return await self._repository.get_all(limit)
    
    async def update_document(self, doc_id: UUID, new_text: str) -> DocumentRecord | None:
        """Actualiza el texto extraído de un documento existente."""
        logger.info(f"Actualizando texto del documento con ID: {doc_id}")
        return await self._repository.update(doc_id, new_text)
    
    async def delete_document(self, doc_id: UUID) -> bool:
        """Elimina un documento del sistema físico de forma permanente."""
        result = await self._repository.delete(doc_id)
        if result:
            logger.info(f"Documento con ID {doc_id} eliminado correctamente.")
        else:
            logger.warning(f"Intento de eliminar documento inexistente (ID: {doc_id})")
        return result