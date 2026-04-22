import uuid
from datetime import datetime, timezone
from tinydb import TinyDB, Query
from app.application.interfaces.summary_repository import SummaryRepository, Summary

class TinyDBSummaryRepository(SummaryRepository):
    def __init__(self, db: TinyDB):
        self.db = db
        # Creamos o usamos una "tabla" (colección NoSQL) llamada 'summaries'
        self.table = db.table('summaries')

    async def save(self, summary: Summary) -> Summary:
        # 1. Si es un documento nuevo, le generamos ID y fecha
        if not summary.id:
            summary.id = uuid.uuid4()
        if not summary.created_at:
            summary.created_at = datetime.now(timezone.utc)

        # 2. Convertimos los datos al formato JSON que usa TinyDB
        doc = {
            "id": str(summary.id),
            "original_filename": summary.original_filename,
            "summary_text": summary.summary_text,
            "full_text": summary.full_text,
            "checksum": summary.checksum,
            "created_at": summary.created_at.isoformat() # Convertimos fecha a texto
        }
        
        # 3. Lo insertamos
        self.table.insert(doc)
        return summary

    async def get_by_id(self, summary_id: uuid.UUID) -> Summary | None:
        Doc = Query()
        result = self.table.search(Doc.id == str(summary_id))
        return self._map_to_summary(result[0]) if result else None

    async def get_all(self, limit: int = 100) -> list[Summary]:
        results = self.table.all()
        # Ordenamos del más nuevo al más viejo
        results.sort(key=lambda x: x["created_at"], reverse=True)
        return [self._map_to_summary(doc) for doc in results[:limit]]

    async def exists_by_checksum(self, checksum: str) -> bool:
        # ✨ ¡Aquí está la magia anti-duplicados! ✨
        Doc = Query()
        return self.table.contains(Doc.checksum == checksum)

    async def delete(self, summary_id: uuid.UUID) -> bool:
        Doc = Query()
        # remove() borra el documento y devuelve cuántos borró
        deleted = self.table.remove(Doc.id == str(summary_id))
        return len(deleted) > 0

    def _map_to_summary(self, data: dict) -> Summary:
        # Función auxiliar para convertir el JSON de vuelta al molde Summary
        return Summary(
            id=uuid.UUID(data["id"]),
            original_filename=data["original_filename"],
            summary_text=data["summary_text"],
            full_text=data["full_text"],
            checksum=data["checksum"],
            created_at=datetime.fromisoformat(data["created_at"])
        )