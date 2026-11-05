import uuid
from datetime import datetime
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError
from app.application.interfaces.document_repository import DocumentRecord, DuplicateDocumentError

_LIST_LIMIT = 100


class MongoDocumentRepository:
    def __init__(self, db: AsyncDatabase):
        self._collection = db["documents"]

    async def ensure_indexes(self) -> None:
        """El índice único evita duplicados aunque dos subidas lleguen a la vez."""
        await self._collection.create_index("checksum", unique=True)

    async def save(self, document: DocumentRecord) -> DocumentRecord:
        doc_dict = {
            "_id": str(document.id),
            "original_filename": document.original_filename,
            "full_text": document.full_text,
            "checksum": document.checksum,
            "created_at": document.created_at.isoformat(),
        }
        try:
            await self._collection.insert_one(doc_dict)
        except DuplicateKeyError as exc:
            raise DuplicateDocumentError() from exc
        return self._map_to_record(doc_dict)

    async def get_by_id(self, doc_id: uuid.UUID) -> DocumentRecord | None:
        doc = await self._collection.find_one({"_id": str(doc_id)})
        return self._map_to_record(doc) if doc else None

    async def get_all(self) -> list[DocumentRecord]:
        cursor = self._collection.find().limit(_LIST_LIMIT)
        docs = await cursor.to_list(length=_LIST_LIMIT)
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
            created_at=datetime.fromisoformat(doc["created_at"]),
        )
