"""
Módulo de servicios de aplicación para la gestión de documentos.
Actúa como orquestador de la lógica de negocio, aplicando el principio de Responsabilidad Única (SRP).
"""
from uuid import UUID
from app.application.interfaces.document_repository import DocumentRecord, DocumentRepository
from app.application.services.pdf_service import PDFService

class DocumentService:
    """
    Coordina las operaciones sobre los documentos interactuando con el extractor de PDF
    y la base de datos, sin conocer los detalles de implementación de ninguno.
    """
    def __init__(self, pdf_service: PDFService, repository: DocumentRepository):
        self._pdf_service = pdf_service
        self._repository = repository

    async def create_document(self, file_content: bytes, filename: str) -> DocumentRecord:
        """
        Procesa un nuevo archivo PDF, extrae su texto y lo guarda en la base de datos.

        Args:
            file_content: El contenido binario del archivo PDF cargado en memoria.
            filename: El nombre original del archivo subido por el usuario.

        Returns:
            DocumentRecord: La entidad del documento guardado con su ID y metadatos.

        Raises:
            ValueError: Si el documento ya existe en la base de datos (Regla de negocio anti-duplicados).
        """
        extracted = self._pdf_service.extract_text(file_content, filename)
        
        # Validamos la regla de negocio del proyecto: evitar duplicados usando el checksum
        if await self._repository.exists_by_checksum(extracted.checksum):
            raise ValueError("Un documento con este mismo contenido ya existe en la base de datos.")
        
        document = DocumentRecord(
            id=None,
            original_filename=filename,
            full_text=extracted.text,
            checksum=extracted.checksum,
            created_at=None,
        )
        return await self._repository.save(document)

    async def get_document(self, doc_id: UUID) -> DocumentRecord | None:
        """Recupera un documento específico mediante su identificador único."""
        return await self._repository.get_by_id(doc_id)

    async def list_documents(self, limit: int = 100) -> list[DocumentRecord]:
        """Obtiene una lista paginada de todos los documentos almacenados."""
        return await self._repository.get_all(limit)
    
    async def update_document(self, doc_id: UUID, new_text: str) -> DocumentRecord | None:
        """Actualiza el texto extraído de un documento existente."""
        return await self._repository.update(doc_id, new_text)
    
    async def delete_document(self, doc_id: UUID) -> bool:
        """Elimina un documento del sistema físico de forma permanente."""
        return await self._repository.delete(doc_id)