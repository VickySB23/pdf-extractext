"""
Contratos de persistencia y entidades de dominio.
Cumple estrictamente con el requerimiento de guardar el texto y el checksum.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from uuid import UUID

@dataclass
class DocumentRecord:
    """Entidad principal: Representa el texto extraído del PDF y su checksum."""
    id: UUID | None
    original_filename: str
    full_text: str
    checksum: str
    created_at: datetime | None

class DocumentRepository(Protocol):
    """Contrato CRUD completo (Create, Read, Update, Delete) para la base de datos."""
    async def save(self, document: DocumentRecord) -> DocumentRecord: ...
    async def get_by_id(self, doc_id: UUID) -> DocumentRecord | None: ...
    async def get_all(self, limit: int = 100) -> list[DocumentRecord]: ...
    async def update(self, doc_id: UUID, new_text: str) -> DocumentRecord | None: ...
    async def delete(self, doc_id: UUID) -> bool: ...
    async def exists_by_checksum(self, checksum: str) -> bool: ...