"""
Módulo de infraestructura para la persistencia de datos.
Implementa el patrón Repository utilizando TinyDB como motor NoSQL para cumplir
con el requerimiento de almacenamiento no relacional del proyecto.
"""
import uuid
from datetime import datetime, timezone
from tinydb import TinyDB, Query
from app.application.interfaces.document_repository import DocumentRepository, DocumentRecord

class TinyDBDocumentRepository(DocumentRepository):
    """
    Adaptador de base de datos que traduce las entidades de dominio (DocumentRecord)
    al formato JSON requerido por TinyDB.
    """
    def __init__(self, db: TinyDB):
        self.db = db
        self.table = db.table('documents')

    async def save(self, document: DocumentRecord) -> DocumentRecord:
        """Persiste un nuevo registro, autogenerando el ID y la fecha de creación si faltan."""
        if not document.id:
            document.id = uuid.uuid4()
        if not document.created_at:
            document.created_at = datetime.now(timezone.utc)

        doc_dict = {
            "id": str(document.id),
            "original_filename": document.original_filename,
            "full_text": document.full_text,
            "checksum": document.checksum,
            "created_at": document.created_at.isoformat()
        }
        self.table.insert(doc_dict)
        return document

    async def get_by_id(self, doc_id: uuid.UUID) -> DocumentRecord | None:
        """Busca un documento por ID. Retorna None para facilitar el manejo de errores HTTP 404."""
        Doc = Query()
        result = self.table.search(Doc.id == str(doc_id))
        return self._map_to_document(result[0]) if result else None

    async def get_all(self, limit: int = 100) -> list[DocumentRecord]:
        """Obtiene la colección de documentos ordenados desde el más reciente al más antiguo."""
        results = self.table.all()
        results.sort(key=lambda x: x["created_at"], reverse=True)
        return [self._map_to_document(doc) for doc in results[:limit]]

    async def update(self, doc_id: uuid.UUID, new_text: str) -> DocumentRecord | None:
        """Actualiza un registro y devuelve el documento resultante para validar el cambio."""
        Doc = Query()
        updated = self.table.update({"full_text": new_text}, Doc.id == str(doc_id))
        return await self.get_by_id(doc_id) if updated else None

    async def delete(self, doc_id: uuid.UUID) -> bool:
        """Elimina físicamente el documento. Devuelve True si se borró al menos un registro."""
        Doc = Query()
        deleted = self.table.remove(Doc.id == str(doc_id))
        return len(deleted) > 0

    async def exists_by_checksum(self, checksum: str) -> bool:
        """Verifica si la huella digital del archivo ya está registrada para evitar duplicados."""
        Doc = Query()
        return self.table.contains(Doc.checksum == checksum)

    def _map_to_document(self, data: dict) -> DocumentRecord:
        """Función auxiliar (privada) para reconstruir la entidad de dominio desde el JSON crudo."""
        return DocumentRecord(
            id=uuid.UUID(data["id"]),
            original_filename=data["original_filename"],
            full_text=data["full_text"],
            checksum=data["checksum"],
            created_at=datetime.fromisoformat(data["created_at"])
        )