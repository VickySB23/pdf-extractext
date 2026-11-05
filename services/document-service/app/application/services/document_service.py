"""
Módulo de servicios de aplicación para la gestión de documentos.
Actúa como orquestador de la lógica de negocio, aplicando el principio de Responsabilidad Única (SRP).
"""
import hashlib
import uuid
from datetime import UTC, datetime
from uuid import UUID

from app.application.interfaces.document_repository import (
    DocumentRecord,
    DocumentRepository,
    DuplicateDocumentError,
)
from app.application.interfaces.text_extractor import NoTextError, TextExtractor
from app.core.logger import logger


class DocumentService:
    def __init__(self, extractor: TextExtractor, repository: DocumentRepository):
        self._extractor = extractor
        self._repository = repository

    async def create_document(self, file_content: bytes, filename: str) -> DocumentRecord:
        logger.info(f"Iniciando procesamiento del documento: '{filename}'")
        extracted = await self._extractor.extract(file_content)

        text = extracted.text.strip()
        if not text:
            logger.warning(f"El documento '{filename}' no contiene texto extraíble.")
            raise NoTextError("No se encontró texto extraíble en el PDF.")

        checksum = hashlib.sha256(file_content).hexdigest()
        logger.info(
            f"Texto extraído de '{filename}' ({extracted.pages} páginas)."
        )

        if await self._repository.exists_by_checksum(checksum):
            logger.warning(f"Rechazado: El documento '{filename}' ya existe (Duplicado de Checksum).")
            raise DuplicateDocumentError()

        document = DocumentRecord(
            id=uuid.uuid4(),
            original_filename=filename,
            full_text=text,
            checksum=checksum,
            created_at=datetime.now(UTC),
        )

        saved_doc = await self._repository.save(document)
        logger.info(f"Documento '{filename}' guardado exitosamente con ID: {saved_doc.id}")
        return saved_doc

    async def get_document(self, doc_id: UUID) -> DocumentRecord | None:
        """Recupera un documento específico mediante su identificador único."""
        return await self._repository.get_by_id(doc_id)

    async def list_documents(self) -> list[DocumentRecord]:
        """Obtiene los documentos almacenados, hasta el tope del repositorio."""
        return await self._repository.get_all()

    async def update_document(self, doc_id: UUID, new_text: str) -> DocumentRecord | None:
        """Actualiza el texto extraído de un documento existente."""
        logger.info(f"Actualizando texto del documento con ID: {doc_id}")
        return await self._repository.update(doc_id, new_text)

    async def delete_document(self, doc_id: UUID) -> bool:
        """Elimina un documento de la base de datos."""
        result = await self._repository.delete(doc_id)
        if result:
            logger.info(f"Documento con ID {doc_id} eliminado correctamente.")
        else:
            logger.warning(f"Intento de eliminar documento inexistente (ID: {doc_id})")
        return result
