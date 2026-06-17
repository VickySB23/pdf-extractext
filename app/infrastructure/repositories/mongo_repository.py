import uuid
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase
from app.application.interfaces.document_repository import DocumentRepository, DocumentRecord

class MongoDocumentRepository(DocumentRepository):
    def __init__(self, db: AsyncIOMotorDatabase):
        self._collection = db["documents"]

    async def save(self, document: DocumentRecord) -> DocumentRecord:
        doc_dict = {
            "_id": str(document.id),
            "original_filename": document.original_filename,
            "full_text": document.full_text,
            "checksum": document.checksum,
            "created_at": document.created_at.isoformat() if document.created_at else datetime.now(timezone.utc).isoformat()
        }
        await self._collection.insert_one(doc_dict)
        return self._map_to_record(doc_dict)

    async def get_by_id(self, doc_id: uuid.UUID) -> DocumentRecord | None:
        doc = await self._collection.find_one({"_id": str(doc_id)})
        return self._map_to_record(doc) if doc else None

    async def get_all(self, limit: int = 100) -> list[DocumentRecord]:
        cursor = self._collection.find().limit(limit)
        docs = await cursor.to_list(length=limit)
        return [self._map_to_record(doc) for doc in docs]

    async def update(self, doc_id: uuid.UUID, new_text: str) -> DocumentRecord | None:
        result = await self._collection.find_one_and_update(
            {"_id": str(doc_id)},
            {"$set": {"full_text": new_text}},
            return_document=True
        )
        return self._map_to_record(result) if result else None

    async def delete(self, doc_id: uuid.UUID) -> bool:
        result = await self._collection.delete_one({"_id": str(doc_id)})
        return result.deleted_count > 0

    async def exists_by_checksum(self, checksum: str) -> bool:
        count = await self._collection.count_documents({"checksum": checksum}, limit=1)
        return count > 0

    def _map_to_record(self, doc: dict) -> DocumentRecord:
        """Convierte el diccionario de MongoDB de vuelta a nuestra Entidad del Dominio."""
        return DocumentRecord(
            id=uuid.UUID(doc["_id"]),
            original_filename=doc["original_filename"],
            full_text=doc["full_text"],
            checksum=doc["checksum"],
            created_at=datetime.fromisoformat(doc["created_at"]) if doc.get("created_at") else None
        )